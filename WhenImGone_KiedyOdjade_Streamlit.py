import streamlit as st
import folium
from streamlit_folium import st_folium, folium_static
import aiohttp
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from config_api import API_KEY


# NAZWA = "When I'm Gone / Kiedy Odjade"

# TODO: add automatic "black" - file reformat
# TODO: check "streamlit-server-state" library


API_KEY = API_KEY
WAWA_API_BUS_JSON = (
    "https://api.um.warszawa.pl/api/action/busestrams_get/?resource_id=f2e5503e-927d-4ad3-9500-4ab9e55deb59&apikey="
    + API_KEY
    + "&type=1"
)

WAWA_API_TRAM_JSON = (
    "https://api.um.warszawa.pl/api/action/busestrams_get/?resource_id=f2e5503e-927d-4ad3-9500-4ab9e55deb59&apikey="
    + API_KEY
    + "&type=2"
)

CENTER_START = [52.23181538050862, 21.006035781379524]
ZOOM_START = 12


# session_state initialization
if "center" not in st.session_state:
    st.session_state.center = CENTER_START
if "zoom" not in st.session_state:
    st.session_state.zoom = ZOOM_START
if "markers" not in st.session_state:
    st.session_state.markers = []

if "last_api_call" not in st.session_state:
    st.session_state.last_api_call = 0
if "map_refresh_counter" not in st.session_state:
    st.session_state.map_refresh_counter = 0
if "last_json_bus" not in st.session_state:
    st.session_state.last_json_bus = 0
if "last_json_tram" not in st.session_state:
    st.session_state.last_json_tram = 0
if "json_errors" not in st.session_state:
    st.session_state.json_errors = 0

if "only_bus" not in st.session_state:
    st.session_state.only_bus = 0
if "only_tram" not in st.session_state:
    st.session_state.only_tram = 0

if "selected_bus_lines" not in st.session_state:
    st.session_state.selected_bus_lines = []
if "selected_tram_lines" not in st.session_state:
    st.session_state.selected_tram_lines = []


def ss_flip():
    if st.session_state.only_bus:
        if st.session_state.only_tram:
            st.session_state.only_bus = 0
            st.session_state.only_tram = 0
    elif st.session_state.only_tram:
        if st.session_state.only_bus:
            st.session_state.only_bus = 0
            st.session_state.only_tram = 0


# get json
async def fetch(session, url):
    try:
        async with session.get(url) as response:
            result = await response.json()
            # print(
            #     f"ZTM API call (type='{url[-1]}'): ",
            #     datetime.now(),
            # )
            st.session_state.last_api_call = datetime.now()
            return result
    except Exception:
        return {}


# convert json to pandas DataFrame + convert "Time" column for future calculation
@st.cache_data
def json_to_pandas(json, last_json, type):
    try:
        pandas_json = pd.json_normalize(json["result"])
        pandas_json["Time"] = pd.to_datetime(pandas_json["Time"])
        if type == "bus":
            st.session_state.last_json_bus = json
        elif type == "tram":
            st.session_state.last_json_tram = json
    except Exception:
        if json["result"] == [] and type == "tram":
            json_zero = {
                "Lines": "0",
                "Lon": 21.006035,
                "VehicleNumber": "0",
                "Time": datetime.now(),
                "Lat": 52.231815,
                "Brigade": "0",
            }
            st.session_state.last_json_tram = json
            return pd.DataFrame(json_zero, index=[0])
        st.session_state.json_errors += 1
        pandas_json = pd.json_normalize(last_json["result"])
        pandas_json["Time"] = pd.to_datetime(pandas_json["Time"])
        # return (print(pandas_json)) -> {'result': 'Błędna metoda lub parametry wywołania'}
    return pandas_json


# get time and filter data from API
@st.cache_data
def filter_data_by_time(wawa_array, marker="globe"):
    # print(wawa_array)
    current_date_and_time = datetime.now()
    wawa_array_filtered = wawa_array.loc[
        wawa_array["Time"] > (current_date_and_time - timedelta(minutes=5))
    ].copy()
    wawa_time = abs(wawa_array_filtered["Time"] - current_date_and_time)
    wawa_time_string = wawa_time.astype("str").str.split().str[-1]
    wawa_time_string = pd.to_datetime(wawa_time_string)
    wawa_array_filtered["LastUpdate"] = wawa_time_string.dt.strftime("%Mm %Ss")
    wawa_array_filtered["Marker"] = marker
    return wawa_array_filtered


# add markers to session_state for interactive map
@st.cache_data
def markers_to_session(wawa_array_filtered, marker_color="white"):
    # del st.session_state.markers
    st.session_state.markers = []

    for ind, row in wawa_array_filtered.iterrows():
        st.session_state.markers.append(
            folium.Marker(
                [row["Lat"], row["Lon"]],
                popup=row["Lines"]
                + "("
                + row["VehicleNumber"]
                + "/"
                + row["Brigade"]
                + ")",
                icon=folium.Icon(color=marker_color, icon=row["Marker"], prefix="fa"),
            )
        )
    return True


# main with logic
async def main():
    st.set_page_config(page_title="When I'm Gone", page_icon="🚌")

    st.title("When I'm Gone / Kiedy Odjade")
    st.write(
        "Simple geo data visualization of ZTM transportation in Warsaw, data from [api.um.warszawa.pl](api.um.warszawa.pl) | \
        [Code](https://github.com/Samox1/WhenImGone-KiedyOdjade)"
    )
    st.write("")

    # total_stop = st.checkbox("Total Stop")
    pandas_all = pd.DataFrame()
    pandas_bus = pd.DataFrame()
    pandas_tram = pd.DataFrame()

    st.session_state.map_refresh_counter += 1

    # get json and convert to pandas DataFrame
    async with aiohttp.ClientSession() as session:
        data_bus = await fetch(session, WAWA_API_BUS_JSON)
        data_tram = await fetch(session, WAWA_API_TRAM_JSON)

        if data_bus:
            pandas_bus = json_to_pandas(data_bus, st.session_state.last_json_bus, "bus")
        else:
            st.error("Error")

        if data_tram:
            pandas_tram = json_to_pandas(
                data_tram, st.session_state.last_json_tram, "tram"
            )
        else:
            st.error("Error")

    # filter data to show markers with "Time" > now - 5min
    pandas_bus = filter_data_by_time(pandas_bus, marker="bus")
    pandas_tram = filter_data_by_time(pandas_tram, marker="train")

    col1, col2, col3 = st.columns(3)
    with col1:
        check_rerun = st.checkbox("Live (2s)", value=True)
    with col2:
        only_bus = st.checkbox("Only BUS", key="only_bus", on_change=ss_flip())
    with col3:
        only_tram = st.checkbox("Only TRAM", key="only_tram", on_change=ss_flip())

    # logic to select only BUS or TRAM
    if only_bus:
        pandas_all = pandas_bus
    elif only_tram:
        pandas_all = pandas_tram
    else:
        pandas_all = pd.concat([pandas_bus, pandas_tram], axis=0)

    # multiselect batton -> saving selection in session_state
    col1_select, col2_select = st.columns(2)
    with col1_select:
        st.session_state.selected_bus_lines = st.multiselect(
            label="Select BUS lines:",
            options=np.sort(pandas_bus["Lines"].unique()),
            default=st.session_state.selected_bus_lines,
            disabled=st.session_state.only_tram,
        )
    with col2_select:
        st.session_state.selected_tram_lines = st.multiselect(
            label="Select TRAM lines:",
            options=np.sort(pandas_tram["Lines"].unique()),
            default=st.session_state.selected_tram_lines,
            disabled=st.session_state.only_bus,
        )

    # use only selected lines -> if 0 selected show all markers
    if (len(st.session_state.selected_bus_lines) > 0) or len(
        st.session_state.selected_tram_lines
    ) > 0:
        pandas_all = pandas_all[
            pandas_all["Lines"].isin(
                st.session_state.selected_bus_lines
                + st.session_state.selected_tram_lines
            )
        ]

    # add markers to state_session
    markers_done = markers_to_session(pandas_all, marker_color="black")

    # map initialization
    m = folium.Map(location=CENTER_START, zoom_start=8)

    fg = folium.FeatureGroup(name="Markers")
    for marker in st.session_state.markers:
        fg.add_child(marker)

    st.write(
        "API last call -> ",
        st.session_state.last_api_call,
        " | API calls in this session: ",
        st.session_state.map_refresh_counter,
        " | API call ERRORS: ",
        st.session_state.json_errors,
    )

    # map render
    map_data = st_folium(
        m,
        center=st.session_state.center,
        zoom=st.session_state.zoom,
        key="new",
        feature_group_to_add=fg,
        height=400,
        width=700,
    )
    # st.write(map_data)

    st.write(
        "Number of vehicles (displayed): ",
        pandas_all.shape[0],
        " | Number of BUSes: ",
        pandas_bus.shape[0],
        " | Number of TRAMs: ",
        pandas_tram.shape[0],
    )

    # show table with selected items
    # st.write(pandas_bus)
    # st.write(pandas_tram)
    st.write(pandas_all)

    ### Sidebar with printed "session_state"
    # with st.sidebar:
    #    st.write(st.session_state)

    ### Total STOP -> not working right now
    # if(total_stop):
    #     print("STOP")
    #     st.stop()

    if check_rerun:
        time.sleep(2)
        st.experimental_rerun()


### --- End of MAIN --- ###


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
