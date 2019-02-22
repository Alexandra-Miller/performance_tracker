import os
import json
import pendulum
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from analyzer.nextBusData import NextBusData
from analyzer.geoHelpers import findRelativePositions, toGDF
from analyzer.tracker import getTrips
from helpers.datetimefs import DateTimeFS, construct_filename
from helpers.timing import (
    get_appropriate_schedule,
    first_scheduled_arrival,
    last_scheduled_arrival,
)

agency = "lametro-rail"
datetime = pendulum.now("America/Los_Angeles")


def process_frame(datetime, path_base):
    source_path = construct_filename(path_base, datetime, ".json")
    with open(source_path, "r") as infile:
        raw_data = json.load(infile)
    try:
        preprocessed = NextBusData(raw_data)
    except:
        return None
    # no need to run any more processing
    # than necessary inside inner loop.
    return preprocessed.vehicles


for line in range(801, 807):
    schedule_path = get_appropriate_schedule(line, agency, datetime, "data/schedule")
    start_datetime = first_scheduled_arrival(schedule_path)
    end_datetime = last_scheduled_arrival(schedule_path)

    path_base = f"data/vehicle_tracking/raw/{line}_{agency}"

    dtfs = DateTimeFS(path_base)

    datetimes = dtfs.get_datetimes_in_range(
        start_datetime.in_tz("UTC"), end_datetime.in_tz("UTC")
    )

    track_0_path = f"data/line_info/{line}/{line}_0.geojson"
    track_1_path = f"data/line_info/{line}/{line}_1.geojson"
    with open(track_0_path) as infile:
        obj = json.load(infile)
        track_0 = LineString(obj["features"][0]["geometry"]["coordinates"])
    with open(track_1_path) as infile:
        obj = json.load(infile)
        track_1 = LineString(obj["features"][0]["geometry"]["coordinates"])

    array = [process_frame(datetime, path_base) for datetime in datetimes]
    cleaned = [x for x in array if x is not None]
    df = pd.concat(cleaned)
    df = df.drop_duplicates(
        subset=["report_time", "latitude", "longitude", "vehicle_id"]
    )
    df = df[df["predictable"] == "true"]
    df["latitude"] = pd.to_numeric(df.latitude)
    df["longitude"] = pd.to_numeric(df.longitude)
    df = toGDF(df)

    mask_0 = (df["direction"] == "0") | (df["direction"] == "90")
    mask_1 = (df["direction"] == "180") | (df["direction"] == "270")
    df_0 = df.loc[mask_0]
    df_1 = df.loc[mask_1]
    df_0["relative_position"] = findRelativePositions(df_0, track_0)
    df_0["direction_id"] = 0
    df_1["relative_position"] = findRelativePositions(df_1, track_1)
    df_1["direction_id"] = 1
    df = pd.concat([df_0, df_1])

    df["datetime"] = pd.to_datetime(df["report_time"], utc=True)
    df["datetime_local_iso8601"] = df.report_time.apply(
        lambda dt: pendulum.parse(dt, tz="UTC")
        .in_tz("America/Los_Angeles")
        .to_iso8601_string()
    )
    df = df.reset_index(drop=True)  # necessary both before and after getTrips
    df = getTrips(df)
    df = df.reset_index(drop=True)  # necessary both before and after getTrips
    df["datetime"] = df["datetime_local_iso8601"]
    df = df[["datetime", "trip_id", "direction_id", "relative_position"]]

    processed_path = f"data/vehicle_tracking/processed/{line}_{agency}"
    os.makedirs(processed_path, exist_ok=True)
    df.to_csv(
        os.path.join(processed_path, start_datetime.format("YYYY-MM-DD")) + ".csv"
    )
