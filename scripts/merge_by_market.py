# ================================== STEP 2 ==================================
from pyspark.sql import functions as F
from merge_by_stock import merge_by_stock
from plot import plot_market, plot_stocks_corona

def merge_by_market(spark, stock_column, stock_markets, covid_column, covid_area, sector, read_path, write_path):
    '''Groups DataFrames for each stock market by Year and Week calculating the average value for stock_column.
    Also merges with Covid data and saves resulting plots in GCS. Returns the list of merged market DataFrames
    and the Covid DataFrame.'''
    # Initialize an empty list for grouped DataFrames
    processed_dfs = []

    # Get Covid data
    covid_df = merge_corona_by_location(spark, covid_column, covid_area, read_path)

    for market in stock_markets:
        # Read and cleanse CSVs for market
        df = merge_by_stock(spark, market, stock_column, read_path)

        print(f'============ Filtering and merging stock market data for {market}... ============')

        # Filter by sector
        if sector != "No specific sector":
            sector_df = spark.read.csv(f"{read_path}/stock_market_data/CategorisedStocks.csv", header=True, inferSchema=True)
            sector_df = sector_df.filter(sector_df.Sector == sector).select("Company")
            df = df.join(sector_df, df['Name'] == sector_df['Company'])

        # Group price/volume by 'Market', 'Year' and 'Week'
        if stock_column == 'Volume':
            df = df.groupBy('Market', 'Year', 'Week').agg(F.sum(stock_column).alias(f"Total_{stock_column}"))
        else:
            df = df.groupBy('Market', 'Year', 'Week').agg(F.avg(stock_column).alias(f"Average_{stock_column}"))

        processed_dfs.append(df)

        # Plot market data alone
        plot_path_market = f"{write_path}/stock_market_data/plots/{market}_{stock_column}.png"
        plot_market(df, stock_column, market, plot_path_market)

        # Plot with Covid data
        merged_df = df.join(covid_df, ["Year", "Week"])
        plot_path_covid = f"{write_path}/stocks_covid_merged/plots/{market}_{stock_column}_{covid_area[1]}.png"
        plot_stocks_corona(merged_df, stock_column, covid_column, market, plot_path_covid)
    
    return processed_dfs, covid_df


def merge_corona_by_location(spark, column, area, read_path):
    '''Filters Covid data by chosen area and groups by Year and Week.'''
    # Read the CSV file into a DataFrame with header and schema inferred
    division = area[0]
    location = area[1]
    df = spark.read.csv(f"{read_path}/covid_death_data/export_{division}.csv", header=True, inferSchema=True)

    # Filter by world / region / country
    df = df.filter(F.col(df.columns[0]) == location)

    # Select only the necessary columns
    df = df.select('date', column)

    # Convert the date string to a date format and extract the week and year
    df = df.withColumn("date", F.to_date(F.col("date"), 'yyyy-MM-dd'))
    df = df.withColumn("Week", F.weekofyear(F.col("date")))
    df = df.withColumn("Year", F.year(F.col("date")))

    # Group by 'year' and 'week_of_year' and then aggregate
    return df.groupBy("Year", "Week").agg(F.avg(F.col(column)).alias("average_" + column))