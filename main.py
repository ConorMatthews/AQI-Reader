# Coded in Python 3.7

import csv
import time
import os
import os.path
import requests
import math
import sds011
import aqi
import PySimpleGUI as sg
import http.client as httplib

from datetime import datetime
from threading import Thread

#### START OF USER CUSTOMISABILITY HERE ####
comparison_data = 'pm25'  # Select the data to be pulled from API can be: pm25, pm10, co, o3, p, so2, t, w
api_token = 'demo'  # You can enter their own API token for use if desired
api_location = 'shanghai'  # You can enter their own location data here
sensor_path = "/dev/ttyUSB0"  # You may need to enter the path of the SDS011 sensor
monitor_size_x = 800  # You can adjust the size of the window created - Make it the same as your screen for full screen
monitor_size_y = 480  # You can adjust the size of the window created - Make it the same as your screen for full screen
#### END OF USER CUSTOMISABILITY HERE ####


api_link = 'http://api.waqi.info/feed/' + api_location + '/?token=' + api_token  # The link to the AQI API


try:
    sensor = sds011.SDS011(sensor_path, use_query_mode=True)
    sensor.sleep()  # Tests sensor is working by placing it in sleep
except:
    sensor = 'NO_SENSOR'



def setUpGUI():  # This is the code that creates and updates the GUI
    sg.ChangeLookAndFeel('BlueMono')  # Colour scheme for window
    live_aqi, time, average_aqi, per_change, live_api = getData()  # Runs the get_data() sub routine to get the data
    average_aqi = average_aqi[0]  # average_aqi holds multiple values, one rounded, one non-rounded
    actual_file_size = os.stat('data.csv').st_size / (1024*1024)
    actual_file_size = "%.4f" % actual_file_size
    max_data = open('max_data_size.txt', 'r')
    max_file_size = max_data.readline()
    max_data.close()

    #  Works out what colours are needed for the GUI segments
    #  tc = text colour, normally white or black
    #  tbc = text background colour, in line with the AQI standard
    tbc, tc = colourCheck(live_aqi)
    tbc2, tc2 = colourCheck(average_aqi)
    try:
        tbc4, tc4 = colourCheck(live_api)
    except:
        tbc4, tc4 = '#ffffff', '#000000'  # white hex value then black
    try:
        if float(per_change) < 0:
            tbc3 = '#00ff00'  # green
        elif float(per_change) > 0:
            tbc3 = '#ff0000'  # red
        else:
            tbc3 = '#ffffff'  # white
    except:
        tbc3 = '#ffffff'  # white

    # This section arranges the columns. They are the individual 4 quarters that will hold the data
    col = [[sg.Text('Live AQI', text_color=tc, background_color=tbc)],
           [sg.Text(live_aqi, text_color=tc, background_color=tbc)]]
    col2 = [[sg.Text('Average AQI', text_color=tc2, background_color=tbc2)],
            [sg.Text(average_aqi, text_color=tc2, background_color=tbc2)]]
    col3 = [[sg.Text('% Change upon Average', text_color='#000000', background_color=tbc3)],
            [sg.Text(per_change + '%', text_color='#000000', background_color=tbc3)]]
    col4 = [[sg.Text('Live Shenzehn AQI', text_color=tc4, background_color=tbc4)],
            [sg.Text(live_api, text_color=tc4, background_color=tbc4)]]

    # The layout variable pulls all the columns and other entities needed in the
    # GUI together
    layout = [[sg.Column(col, background_color=tbc),
               sg.VerticalSeparator(pad=None),
               sg.Column(col2, background_color=tbc2)],
              [sg.Text('_' * 30)],
              [sg.Column(col3, background_color=tbc3),
               sg.VerticalSeparator(pad=None),
               sg.Column(col4, background_color=tbc4)],
              [sg.Text('Max data file size (MB):'), sg.InputText(), sg.OK(), sg.Button('Close Window')],
              [sg.Text('Last reading at: ' + time)],
              [sg.Text('Data File Size (MB): ' + str(actual_file_size) + ' / ' + str(max_file_size))]]

    # This section handles all the window functions
    # It creates the window then listens for the user input box
    event, values = sg.Window('Air Quality Index Monitor',
                              layout,
                              auto_close=True,
                              auto_close_duration=10,
                              keep_on_top=False,
                              size=(monitor_size_x, monitor_size_y)).Read()

    if event == 'Close Window':  # Checks to see if the button pressed was the close window button
        return 'close'  # Returns the text 'close' to be picked up by the while loop at the end
    elif event == 'OK':
        if values == '':
            pass
        else:
            try:
                int(values[0])
                max_data_file = open('max_data_size.txt', 'w')
                max_data_file.write(values[0])
                max_data_file.close()
                sg.popup('New max data file size of: ' + values[0] + 'MB')
            except:
                sg.popup('Your input can only contain', 'whole numbers.')


#  This section is largely unnecessary however it will help clean up the GUI section
def getData():
    # Sorts out the multiple values in the live_AQI return
    live_aqi = liveAQI()
    time = live_aqi[1]
    live_aqi = live_aqi[0]

    # Gets the rest of the data into variables
    average_aqi = averageAQI()
    per_change = perChange()
    live_api = liveAPI()
    return live_aqi, time, average_aqi, per_change, live_api  # Returns the data to wherever it was called


# This section is designed to find the last line of the CSV data file
def liveAQI():
    try:
        if os.path.exists('data.csv'):
            with open('data.csv') as csv_file:  # Opens the data file
                csv_reader = csv.reader(csv_file, delimiter=',')  # Sets up the csv parameters for the data file
                for row in csv_reader:  # Gets the final line in the data file for the most up to date reading
                    data_reading = row[0]
                    unix = row[1]
                time_stamp = datetime.utcfromtimestamp(math.trunc(float(unix))).strftime('%H:%M:%S, %d-%m-%Y')
                csv_file.close()  # Closes the data file to avoid complication if the file is not closed
            return data_reading, time_stamp
        else:
            return 'NO DATA', 'NO DATA'
    except:  # Caches all errors in case of corruption in the data file
        return 'NO DATA', 'NO DATA'


def averageAQI():
    try:
        if os.path.exists('data.csv'):
            with open('data.csv') as csv_file:  # Opens the data file
                csv_reader = csv.reader(csv_file, delimiter=',')  # Sets up the csv parameters for the data file
                average_aqi = 0
                lines = 0
                for row in csv_reader:
                    lines = lines + 1
                    average_aqi = average_aqi + int(row[0])
                csv_file.close()
            average_aqi = average_aqi / lines
            rounded_aqi = "%.2f" % average_aqi  # Rounds the number
            return rounded_aqi, average_aqi  # Returns both a rounded number and a non rounded number.
        else:
            return 'NO DATA', 'NO DATA'
    except:
        return 'NO DATA', 'NO DATA'


def perChange():
    try:
        current = liveAQI()
        current = int(current[0])  # Two lines combined into one to get the second item in current
        average = averageAQI()
        average = int(average[1])  # Two lines combined into one to get the un-rounded average
        difference = int(current) - int(average)  # Gets the difference between the new and old values
        perchange = (difference / average) * 100
        return "%.2f" % perchange  # Rounds the perchange value to 2 decimal places and returns the value
    except:
        return 'NO DATA'


def liveAPI():
    if not isConnected():  # Makes sure the device is connected
        return 'NO CONNECTION'
    response = requests.get(api_link)  # Gets the json from the API
    try:
        text = response.json()  # Modifies the json so it can be easily understood by python
        # gets the data needed from the json
        text = text['data']
        text = text['iaqi']
        text = text[comparison_data]
        live_aqi = text['v']
        return live_aqi  # Returns the value from the json
    except:
        return 'NO CONNECTION'


def colourCheck(number):
    try:
        if float(number) <= 50:
            return '#00ff00', '#000000'  # First is green, second is black
        elif float(number) <= 100:
            return '#ffff00', '#000000'  # First is yellow, second is black
        elif float(number) <= 150:
            return '#ffa500', '#000000'  # First is orange, second is black
        elif float(number) <= 200:
            return '#ff0000', '#000000'  # First is red, second is black
        elif float(number) <= 300:
            return '#800080', '#ffffff'  # First is purple, second is white
        elif float(number) <= 500:
            return '#800000', '#ffffff'  # First is maroon, second is white
        else:
            return '#ffffff', '#000000'  # First is white, second is black
    except:
        return '#ffffff', '#000000'  # First is white, second is black


def isConnected():  # Designed to make sure the device is able to connect to the internet
    conn = httplib.HTTPConnection("www.google.com", timeout=5)  # Sets up the site to connect to with a timeout of 5 sec
    try:  # Will try to run in this section - if it cannot it will switch to the except statement.
        conn.request("HEAD", "/")  # Requests a connection to the sit
        conn.close()  # Closes the connection
        return True
    except:
        return False


def saveData():
    while True:
        max_data = open('max_data_size.txt', 'r')
        max_size = max_data.readline()
        max_data.close()
        start = time.time()  # takes unix time at start of using sensor to ensure stable readings
        try:
            ppm25 = sensor.query()[0]  # Query the sensor and then grabs the pm25 result from the list
            # The below lines figure out if the number can be converted to a AQI number. Must be 500 or below
            if ppm25 < 500:
                iaqi = aqi.to_iaqi(aqi.POLLUTANT_PM25, ppm25, algo=aqi.ALGO_EPA)  # Converts micrograms per m^3 to aqi
            else:
                iaqi = 500  # If ppm25 is bigger than 500 iaqi is automatically 500
        except:
            ppm25 = 'NO_DATA'
        data_file_size = os.stat('data.csv').st_size / (1024*1024)
        while float(max_size) <= data_file_size:  # While the size of the file is bigger than the max file size
            lines = list()  # makes empty list
            with open('data.csv', 'r') as readFile:  # Opens the data file
                reader = csv.reader(readFile)  # reads file into variable
                for row in reader:  # appends all lines into the list
                    lines.append(row)
                for line in lines:  # Deletes the first line from the list
                    lines.remove(line)
                    break  # has to break out of loop so as only to delete the first line from the list
            with open('data.csv', 'w', newline='') as writeFile:  # opens the file as write
                writer = csv.writer(writeFile)  # makes csv writer object
                writer.writerows(lines)  # writes the list to the file without the first item
        if ppm25 != 'NO_DATA':
            toappend = [iaqi, time.time()]  # Data formatted ready to be appended to the data file
            with open('data.csv', 'a+', newline='') as appendFile:
                append = csv.writer(appendFile)
                append.writerow(toappend)
        end = time.time()  # Takes time at end to ensure stable reading from sensor
        difference = 3 - (end - start)
        if difference > 0:
            time.sleep(difference)  # Ensures that the readings from the sensor are equally spaced apart


# This section, whilst currently unused, will allow future devs to easily make statements before the data code is ran.
def concurrencySetupData():
    saveData()  # Calls the save data


def concurrencySetupGui():
    while True:
        if setUpGUI() == 'close':
            try:
                sensor.sleep()  # Tries to place the sensor into a sleep state while not using it
                exit()
            except:
                exit()


if __name__ == '__main__':
    # Ensures that two files are available to use fro the program - if they don't exit it creates them
    max_data_file = open('max_data_size.txt', 'a+')
    if os.path.getsize('max_data_size.txt') == 0:
        max_data_file.write('10')  # If the file contains nothing, a max size is auto set.
    data_file = open('data.csv', 'a+')
    max_data_file.close()
    data_file.close()

    # This is the opening statement where 'threads' are created to run the two sections at the same time
    if sensor != 'NO_SENSOR':  # Ensures that there is a sensor before sending bits to it
        sensor.sleep(sleep=False)  # Takes the sensor out of sleep and starts the fan and diode up
        time.sleep(10)  # Gives the sensor time to warm up and generate a stable query - 15 seconds
        Thread(target=concurrencySetupData).start()  # Starts the data collection thread
        Thread(target=concurrencySetupGui).start()  # Starts the GUI thread
    else:  # Accounts for having no sensor attached
        Thread(target=concurrencySetupGui).start()  # Starts the GUI thread
