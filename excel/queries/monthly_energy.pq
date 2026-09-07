let
    Parameters = Excel.CurrentWorkbook(){[Name = "GridSightParameters"]}[Content],
    ProjectRoot = Text.Trim(Parameters{[Parameter = "ProjectRoot"]}[Value]),
    RelativePath = Text.Trim(Parameters{[Parameter = "SampleRelativePath"]}[Value]),
    SourcePath = ProjectRoot & "\\" & Text.Replace(RelativePath, "/", "\\"),
    Source = Csv.Document(
        File.Contents(SourcePath),
        [Delimiter = ",", Columns = 20, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    TypedColumns = Table.TransformColumnTypes(
        PromotedHeaders,
        {
            {"month_key", Int64.Type},
            {"month_start", type date},
            {"calendar_year", Int64.Type},
            {"month_number", Int64.Type},
            {"month_name", type text},
            {"observed_day_count", Int64.Type},
            {"observed_hour_count", Int64.Type},
            {"grid_load_mwh", type number},
            {"average_grid_load_mw", type number},
            {"peak_grid_load_mw", type number},
            {"reported_generation_mwh", type number},
            {"renewable_generation_mwh", type number},
            {"conventional_generation_mwh", type number},
            {"storage_generation_mwh", type number},
            {"renewable_share_of_reported_generation_percent", type number},
            {"average_day_ahead_price_eur_per_mwh", type number},
            {"minimum_day_ahead_price_eur_per_mwh", type number},
            {"maximum_day_ahead_price_eur_per_mwh", type number},
            {"negative_price_hour_count", Int64.Type},
            {"unavailable_generation_value_count", Int64.Type}
        },
        "en-US"
    ),
    AddedYearMonth = Table.AddColumn(
        TypedColumns,
        "year_month",
        each Date.ToText([month_start], "yyyy-MM", "en-US"),
        type text
    ),
    AddedGridLoadTWh = Table.AddColumn(
        AddedYearMonth,
        "grid_load_twh",
        each [grid_load_mwh] / 1000000,
        type number
    ),
    AddedAverageLoadGW = Table.AddColumn(
        AddedGridLoadTWh,
        "average_grid_load_gw",
        each [average_grid_load_mw] / 1000,
        type number
    ),
    AddedPeakLoadGW = Table.AddColumn(
        AddedAverageLoadGW,
        "peak_grid_load_gw",
        each [peak_grid_load_mw] / 1000,
        type number
    ),
    AddedRenewableTWh = Table.AddColumn(
        AddedPeakLoadGW,
        "renewable_generation_twh",
        each [renewable_generation_mwh] / 1000000,
        type number
    ),
    AddedConventionalTWh = Table.AddColumn(
        AddedRenewableTWh,
        "conventional_generation_twh",
        each [conventional_generation_mwh] / 1000000,
        type number
    ),
    AddedStorageTWh = Table.AddColumn(
        AddedConventionalTWh,
        "storage_generation_twh",
        each [storage_generation_mwh] / 1000000,
        type number
    ),
    AddedNegativePriceShare = Table.AddColumn(
        AddedStorageTWh,
        "negative_price_hour_share",
        each [negative_price_hour_count] / [observed_hour_count],
        Percentage.Type
    ),
    AddedWeightedPrice = Table.AddColumn(
        AddedNegativePriceShare,
        "price_hour_weighted_sum",
        each [average_day_ahead_price_eur_per_mwh] * [observed_hour_count],
        type number
    )
in
    AddedWeightedPrice
