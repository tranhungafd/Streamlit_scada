import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, date, time
from pydruid.db import connect

st.set_page_config(layout="wide")
pd.set_option('display.max_colwidth', None)


conn = connect(host='124.158.4.142', port=8888)
cursor = conn.cursor()

# Thanh bên trái (Sidebar)
device = st.sidebar.selectbox(
    'Chọn ID thiết bị:',
    ('66d92f94b7f41dd37df0634a', '66d92fabb7f41dd37df06351', '66d92fc2b7f41dd37df06355', 
     '66d92fc6b7f41dd37df06359', '66d92fcbb7f41dd37df0635d', '66d92fcfb7f41dd37df06361'))
mapping = {
    'Áp lực': "('Pressure','Pressure1', 'P', 'PS1')",
    'Lưu lượng thuận': "('Flow 1', 'Flow1', 'Q', 'FF1')"}
metric = st.sidebar.selectbox(
    'Chọn chỉ số:',
    ('Áp lực', 'Lưu lượng thuận'))

# Giá trị mặc định cho ngày và giờ
default_start_date = date.today()
default_end_date = date.today()
default_start_time = time(0, 0)  # 00:00
max_end_time = time(23, 59)  # 23:59 (thay thế cho 24:00)

# Tạo lựa chọn ngày bắt đầu và ngày kết thúc
start_date = st.sidebar.date_input('Chọn ngày bắt đầu:', default_start_date)
start_time = st.sidebar.time_input('Chọn giờ bắt đầu:', default_start_time)

end_date = st.sidebar.date_input('Chọn ngày kết thúc:', default_end_date)
end_time = st.sidebar.time_input('Chọn giờ kết thúc:', max_end_time)

# Kết hợp ngày và giờ thành định dạng `datetime`
start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

# Kiểm tra logic: nếu ngày bắt đầu và ngày kết thúc là cùng một ngày
if end_date == start_date and end_time < start_time:
    st.error("Thời gian kết thúc không thể nhỏ hơn thời gian bắt đầu. Vui lòng chọn lại.")
else:
    col1, col2 = st.columns(2)
    with col1:
        # Hiển thị thông tin người dùng đã chọn
        st.write(f'**Thiết bị đã chọn:** {device}')
        st.write(f'**Thời gian bắt đầu:** {start_datetime.strftime("%Y/%m/%d %H:%M:%S")}')
    with col2:
        st.write(f'**Chỉ số đã chọn:** {metric}')
        st.write(f'**Thời gian kết thúc:** {end_datetime.strftime("%Y/%m/%d %H:%M:%S")}')
    

    sql = f"""
    SELECT
    "__time", "deviceid", "parameter_key", "dbl_v"
    FROM "scadawater_measuredata"
    WHERE "__time" BETWEEN '{start_date}T{start_time}' AND '{end_date}T{end_time}'
    AND "deviceid" = '{device}'
    AND "parameter_key" IN {mapping[metric]}
    """

    cursor.execute(sql)
    results = cursor.fetchall()
    df = pd.DataFrame(results, columns=[desc[0] for desc in cursor.description])
    df =df.drop_duplicates()

    col1, col2 = st.columns(2)

    # Đặt nội dung vào từng cột
    with col1:
        st.markdown("## Information data")
        st.dataframe(df)   
    
    df['datetime'] = pd.to_datetime(df['__time'])
    df['minute'] = df['datetime'].dt.minute
    df['hour']   = df['datetime'].dt.hour
    df['minute'] = df['minute'] + df['hour']*60

    if(metric == 'Áp lực'):
        Alarm = pd.read_csv(f'Confident_range\Áp lực\{device}.csv')
    else:
        Alarm = pd.read_csv(f'Confident_range\Lưu lượng thuận\{device}.csv')

    with col2: 
        st.markdown("## Confident Range")
        st.dataframe(Alarm)
    
    df_new = pd.merge(df, Alarm, on='minute', how='left')
    df_new["Alarm"] = (df_new["dbl_v"] < df_new["conf_lower"]) | (df_new["dbl_v"] > df_new["conf_upper"])
    df_new["Percent"] = 0
    # Điều kiện khi true_label nhỏ hơn conf_lower (lệch xuống)
    if(np.all(df_new["conf_lower"] != 0)):
        df_new.loc[df_new["dbl_v"] < df_new["conf_lower"], "Percent"] = (df_new["conf_lower"] - df_new["dbl_v"]) / df_new["conf_lower"] * 100
    else:
        df_new.loc[df_new["dbl_v"] < df_new["conf_lower"], "Percent"] = 100
    # Điều kiện khi true_label lớn hơn conf_upper (lệch lên)
    df_new.loc[df_new["dbl_v"] > df_new["conf_upper"], "Percent"] = (df_new["dbl_v"] - df_new["conf_upper"]) / df_new["conf_upper"] * 100
    df_new["Percent"] = round(df_new["Percent"],2)
    df_new = df_new[["__time", "minute", "deviceid", "parameter_key", "dbl_v", "Alarm", "Percent"]]
    data_alarm = df_new[df_new['Alarm'] == True]

    st.markdown("## Plotly")
    plt.figure(figsize=(20, 8))
    plt.scatter(df['minute'],df['dbl_v'], color = "blue")
    plt.scatter(data_alarm['minute'],data_alarm['dbl_v'], color = "red")
    plt.plot(Alarm['minute'], Alarm['conf_upper'], color = "orange", linewidth = 3)
    plt.plot(Alarm['minute'], Alarm['conf_lower'], color = "orange", linewidth = 3)
    plt.title(f"minute vs dbl_v")
    plt.xlabel("Minute")
    plt.ylabel("dbl_v")
    st.pyplot(plt)


    col1, col2 = st.columns(2)
    with col1:
        st.markdown("## Data")
        st.dataframe(df_new[["__time", "deviceid", "parameter_key", "dbl_v", "Alarm", "Percent"]])
    with col2:
        st.markdown("## Alarm Data")
        st.dataframe(data_alarm[["__time", "deviceid", "parameter_key", "dbl_v", "Alarm", "Percent"]])

