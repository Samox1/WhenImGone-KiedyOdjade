import streamlit as st
import folium
from streamlit_folium import st_folium, folium_static
import aiohttp
import asyncio
import pandas as pd
from datetime import datetime, timedelta
import time


# NAZWA = "Kiedy Odjade"

API_KEY = "641871fa-09f4-4925-8352-260938471590"
WAWA_API_BUS_JSON = (
    "https://api.um.warszawa.pl/api/action/busestrams_get/?resource_id=f2e5503e-927d-4ad3-9500-4ab9e55deb59&apikey="
    + API_KEY
    + "&type=1"
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
if "last_json" not in st.session_state:
    st.session_state.last_json = {}
if "json_errors" not in st.session_state:
    st.session_state.json_errors = 0

if "selected_bus" not in st.session_state:
    st.session_state.selected_bus = []
if "selected_tram" not in st.session_state:
    st.session_state.selected_tram = []


# get json
async def fetch(session, url):
    try:
        async with session.get(url) as response:
            result = await response.json()
            print("API call date: ", datetime.now())
            st.session_state.last_api_call = datetime.now()
            return result
    except Exception:
        return {}


# convert json to pandas DataFrame + convert "Time" column for future calculation
@st.cache
def json_to_pandas(json, last_json):
    try:
        pandas_json = pd.json_normalize(json["result"])
    except Exception:
        st.session_state.json_errors += 1
        pandas_json = pd.json_normalize(last_json["result"])
        print(json)
        # return (print(pandas_json)) -> {'result': 'Błędna metoda lub parametry wywołania'}

    pandas_json["Time"] = pd.to_datetime(pandas_json["Time"])
    return pandas_json


# get time and filter data from API
@st.cache
def filter_data_by_time(wawa_bus_array):
    current_date_and_time = datetime.now()
    # wawa_bus_array_filter_time = abs(wawa_bus_array["Time"] - current_date_and_time)
    wawa_bus_array_filtered = wawa_bus_array.loc[
        wawa_bus_array["Time"] > (current_date_and_time - timedelta(minutes=5))
    ]
    return wawa_bus_array_filtered


# add markers to session_state for interactive map
@st.cache
def markers_to_session(wawa_bus_array_filtered):
    del st.session_state.markers
    st.session_state.markers = []

    for ind, row in wawa_bus_array_filtered.iterrows():
        st.session_state.markers.append(
            folium.Marker(
                [row["Lat"], row["Lon"]],
                popup=row["Lines"]
                + "("
                + row["VehicleNumber"]
                + "/"
                + row["Brigade"]
                + ")",
                icon=folium.Icon(color="green", icon="bus", prefix="fa"),
            )
        )
    return True


async def main():
    st.set_page_config(page_title="Kiedy Odjade", page_icon="🚌")

    st.title("Kiedy Odjade / When I'm Gone")

    check_rerun = st.checkbox("Live (2s)")
    # total_stop = st.checkbox("Total Stop")
    pandas_bus = 0

    # get json and convert to pandas DataFrame
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, WAWA_API_BUS_JSON)
        st.session_state.map_refresh_counter += 1

        if data:
            pandas_bus = json_to_pandas(data, st.session_state.last_json)
            st.session_state.last_json = data
        else:
            st.error("Error")

    # filter data to show markers with "Time" > now - 5min
    pandas_bus = filter_data_by_time(pandas_bus)

    # multiselect batton -> saving selection in session_state
    st.session_state.selected_bus = st.multiselect(
        label="Wybierz linie BUS",
        options=pandas_bus["Lines"].unique(),
        default=st.session_state.selected_bus,
    )

    # use only selected bus lines -> if 0 selected show all markers
    if len(st.session_state.selected_bus) > 0:
        pandas_bus = pandas_bus[pandas_bus["Lines"].isin(st.session_state.selected_bus)]

    # add markers to state_session
    markers_done = markers_to_session(pandas_bus)

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

    # show table with selected items
    st.write(pandas_bus)

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
