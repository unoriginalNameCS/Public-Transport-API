#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
COMP9321 24T1 Assignment 2
Data publication as a RESTful service API

Getting Started
---------------

1. You MUST rename this file according to your zID, e.g., z1234567.py.

2. To ensure your submission can be marked correctly, you're strongly encouraged
   to create a new virtual environment for this assignment.  Please see the
   instructions in the assignment 1 specification to create and activate a
   virtual environment.

3. Once you have activated your virtual environment, you need to install the
   following, required packages:

   pip install python-dotenv==1.0.1
   pip install google-generativeai==0.4.1

   You may also use any of the packages we've used in the weekly labs.
   The most likely ones you'll want to install are:

   pip install flask==3.0.2
   pip install flask_restx==1.3.0
   pip install requests==2.31.0

4. Create a file called `.env` in the same directory as this file.  This file
   will contain the Google API key you generatea in the next step.

5. Go to the following page, click on the link to "Get an API key", and follow
   the instructions to generate an API key:

   https://ai.google.dev/tutorials/python_quickstart

6. Add the following line to your `.env` file, replacing `your-api-key` with
   the API key you generated, and save the file:

   GOOGLE_API_KEY=your-api-key

7. You can now start implementing your solution. You are free to edit this file how you like, but keep it readable
   such that a marker can read and understand your code if necessary for partial marks.

Submission
----------

You need to submit this Python file and a `requirements.txt` file.

The `requirements.txt` file should list all the Python packages your code relies
on, and their versions.  You can generate this file by running the following
command while your virtual environment is active:

pip freeze > requirements.txt

You can submit the two files using the following command when connected to CSE,
and assuming the files are in the current directory (remember to replace `zid`
with your actual zID, i.e. the name of this file after renaming it):

give cs9321 assign2 zid.py requirements.txt

You can also submit through WebCMS3, using the tab at the top of the assignment
page.

"""

# You can import more modules from the standard library here if you need them
# (which you will, e.g. sqlite3).
import os
from pathlib import Path

# You can import more third-party packages here if you need them, provided
# that they've been used in the weekly labs, or specified in this assignment,
# and their versions match.
from dotenv import load_dotenv          # Needed to load the environment variables from the .env file
import google.generativeai as genai     # Needed to access the Generative AI API
from flask import Flask, jsonify, request, send_file
from flask_restx import Resource, Api, fields, reqparse, inputs
import requests
from datetime import datetime
import sqlite3
import pprint
import random

studentid = Path(__file__).stem         # Will capture your zID from the filename.
db_file   = f"{studentid}.db"           # Use this variable when referencing the SQLite database file.
txt_file  = f"{studentid}.txt"          # Use this variable when referencing the txt file for Q7.


# Load the environment variables from the .env file
load_dotenv()

# Configure the API key
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Create a Gemini Pro model
gemini = genai.GenerativeModel('gemini-pro')

# Initialise flask app
app = Flask(__name__)
api = Api(app)

# initalise db
conn = sqlite3.connect(db_file, check_same_thread=False)

# initialise cursor
cursor = conn.cursor()

# create table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stops'")
existing_table = cursor.fetchone()
if existing_table is None:
    cursor.execute("""CREATE TABLE stops (
                       stop_id INTEGER,
                   name TEXT,
                   latitude REAL,
                   longitude REAL,
                   last_updated TEXT,
                   self_link TEXT,
                   prev_link TEXT,
                   next_link TEXT
                    )""")

# Commit command
conn.commit()

# initialise q1 parser
q1_parser = reqparse.RequestParser()
# add a query arg to q1_parser
q1_parser.add_argument('query', type=str)



@api.route('/stops')
class QueryStops(Resource):
    @api.doc(responses={
        200: 'Success',
        201: 'Created',
        400: 'Bad Request',
        404: 'Not Found',
        503: 'Service Unavailable',
    },
    description='Get all stops matching the query.')
    @api.expect(q1_parser)
    def put(self):
        args = q1_parser.parse_args()
        q = args.get('query') 
        # this should return a 400 error if somehow query is mispelt
        if (not q):
            return {
                "Error Code": 404,
                "Message": "Bad Request" 
            }, 400
        res = requests.get(f"http://v6.db.transport.rest/locations?poi=false&addresses=false&query={q}&results=5")

        # response codes 400 and 503
        if (res.status_code == 400):
            return 'Bad Request', 400
        elif (res.status_code == 503):
            return 'Service unavailable', 503
        
        l = res.json()
        # remove all the items that are not stops (removes stations)
        for index, ret in enumerate(l):
            if (ret['type'] != 'stop'):
                l.pop(index)

        # Empty so 404 (nothing found by querying)
        if (len(l) == 0):
            return 'Not found', 404

        # put the data in the format that is defined by spec
        formatted_list = []
        if (len(l) > 0):
            for item in l:
                thisItem = {
                    "stop_id": item['id'],
                    "name": item['name'],
                    "latitude": item['location']['latitude'],
                    "longitude": item['location']['longitude'],
                    "last_updated": datetime.now().strftime("%Y-%m-%d-%H:%M:%S"),
                    "_links": {
                        "self": {
                            "href": f"http://localhost:5000/stops/{item['id']}",
                        },
                    },
                }
                formatted_list.append(thisItem)
        
        
        # sort list by stop_id
        sorted_list = sorted(formatted_list, key=lambda x: x['stop_id'])

        # boolean to keep track if a new value is to be added into the db (helpful for response code)
        new_value_added = False

        # iterate through returned array of stops
        for stop in sorted_list:
            # check if the stop already exists in the db
            check_if_stop_exists = cursor.execute(f"SELECT stop_id from stops WHERE stop_id='{stop['stop_id']}'")
            check_if_stop_exists = check_if_stop_exists.fetchone()
            # if it does not exist in the database, then add it
            if (check_if_stop_exists is None):
                print(f"This {stop['stop_id']} does not exist in the db, so we\'ll add it in")
                cursor.execute(f"""INSERT INTO stops(stop_id, name, latitude, longitude, last_updated, self_link)
                               VALUES ('{stop['stop_id']}', '{stop['name']}', '{stop['latitude']}', '{stop['longitude']}', '{stop['last_updated']}', '{stop['_links']['self']['href']}')""")
                # set boolean to True cause a new value is added
                new_value_added = True
                
                conn.commit()
            else:
                # The Stop exists in our database, so we update the last_updated time
                cursor.execute(f"""UPDATE stops SET last_updated='{datetime.now().strftime("%y-%m-%d-%H:%M:%S")}' WHERE stop_id='{stop['stop_id']}'""")
                conn.commit()

        # remove unnecessary fields for spec (latitude, longitude, name)
        # even though these fields aren't need for q1, helpful to store them in db
        for bahn in sorted_list:
            del bahn['latitude']
            del bahn['longitude']
            del bahn['name']

        # update links of all the rows
        current_rows = []
        # Get all the table records of stops ordered by stop_id
        cursor.execute("SELECT * FROM stops ORDER BY stop_id")
        rows = cursor.fetchall()
        # convert the tuples that fetchall returns into dictionaries
        for row in rows:
            convert_row_to_dict = {
                "stop_id": row[0], # the first item should be a stop_id
                "name": row[1], # second item should be name of the stop
                "latitude": row[2], # third item should be latitude
                "longitude": row[3], # 4th item should be longitude
                "last_updated": row[4], # 5th item should be last_updated
                "self_link": row[5], # self link
                "prev_link": row[6], # prev link
                "next_link": row[7], # next link
            }
            current_rows.append(convert_row_to_dict)

        # iterate through the list of dictionaries
        # set prev_link to the row index before it
        # set the next_link to the row index after it
        # for the last dictionary set next_link to Null
        # for the first dictioanry set prev_link to Null
        for index, element in enumerate(current_rows):
            # for first item in the list, set the prev_link to Null
            if (index == 0 and len(current_rows) > 1):
                element['prev_link'] = None
                element['next_link'] = f"{current_rows[index+1]['self_link']}"
            elif (index + 1 < len(current_rows)):
                element['prev_link'] = f"{current_rows[index-1]['self_link']}"
                element['next_link'] = f"{current_rows[index+1]['self_link']}"
            elif (index == len(current_rows) - 1):
                element['prev_link'] = f"{current_rows[index-1]['self_link']}"
                element['next_link'] = None


            # update it in the db
            cursor.execute(f"""UPDATE stops SET next_link='{element['next_link']}' where stop_id='{element['stop_id']}'""")
            cursor.execute(f"""UPDATE stops SET prev_link='{element['prev_link']}' where stop_id='{element['stop_id']}'""")
            conn.commit()
                
        
        # Response code when a new value is added to the database is 201 Created
        if (new_value_added == True):
            return sorted_list, 201
        else:
            return sorted_list, 200
        

# add include arg to q2_parser
q2_parser = reqparse.RequestParser()
q2_parser.add_argument('include', type=str, required=False)

# add selected method to update the field(s) of a stop
q5_parser = reqparse.RequestParser()
# the updatable fields are 'name', 'last_updated', 'latitude', 'longitude', 'next_departure'
q5_parser.add_argument('name', type=str, location='form')
q5_parser.add_argument('last_updated', type=str, location='form')
q5_parser.add_argument('latitude', type=str, location='form')
q5_parser.add_argument('longitude', type=str, location='form')
q5_parser.add_argument('next_departure', type=str, location='form')

my_fields = api.model('MyModel', {
    'name': fields.String
})

@api.route('/stops/<int:stop_id>')
class Stop(Resource):
    @api.doc(responses={
        200: 'Success',
        400: 'Bad Request',
        404: 'Not Found',
        503: 'Service Unavailable',
    },
    description="Get info about a singular stop in the database")
    @api.expect(q2_parser)
    def get(self, stop_id):
        # check if the given stop_id is contained within the database
        check_if_stop_exists = cursor.execute(f"SELECT stop_id, last_updated, name, latitude, longitude, self_link, prev_link, next_link FROM stops WHERE stop_id='{stop_id}'")
        check_if_stop_exists = check_if_stop_exists.fetchall()
        # the stop does not exist in the database, so 404 error
        if (not check_if_stop_exists):
            return {
                "Error Code": 404,
                "Message": f"The stop id of {stop_id} does not exist in the database"
            }, 404
        
        # The stop exists so format the data into a dictionary
        formatted_stop = {
            "stop_id": check_if_stop_exists[0][0],
            "last_updated": check_if_stop_exists[0][1],
            "name": check_if_stop_exists[0][2],
            "latitude": check_if_stop_exists[0][3],
            "longitude": check_if_stop_exists[0][4],
            "next_departure": None,
            "self_link": check_if_stop_exists[0][5],
            "prev_link": check_if_stop_exists[0][6],
            "next_link": check_if_stop_exists[0][7],
        }

        # if the include param is used
        args = q2_parser.parse_args()
        q = args.get('include')
        # 'include param used
        if (q):
            # split the include params by comma to get all params
            params = q.split(',')
            
            # check for _links and _stop_id in query params, if they exist return error
            if ("_links" in params or "stop_id" in params):
                return {
                    "Error": 400,
                    "Message": "Bad request, '_links' and 'stop_id' not permitted parameters"
                }
            
            # go through params to check if given a param that is not allowed
            allowed_params = ["name", "last_updated", "latitude", "longitude", "next_departure"]
            for p in params:
                if p not in allowed_params:
                    return {
                    "Error": 400,
                    "Message": f"Bad request, {p} not permitted parameter"
                }
            
            # make basic return dictionary for every include
            param_formatted_stop = {
                "stop_id": formatted_stop['stop_id'],
                "_links": {
                    "self": {
                        "href": formatted_stop['self_link']
                    },
                    "next": {
                        "href": formatted_stop['next_link']
                    },
                    "prev": {
                        "href": formatted_stop['prev_link']
                }
                }
            }

            # if next_departure in params
            if ("next_departure" in params):
                res = requests.get(f"https://v6.db.transport.rest/stops/{formatted_stop['stop_id']}/departures?duration=120")
                # if service unavailable
                if (res.status_code == 503):
                    return {
                        "Error": 503,
                        "Message": "Service unavailable"
                    }
                l = res.json()
                l = l['departures']
                if (len(l) == 0):
                    return {
                        "Error": 404,
                        "Message": f"Did not find any departures from {formatted_stop['stop_id']} within 120 mins",
                    }, 404
                
                # iterate through list and find the first one where the platform and direction is not none
                found = False
                for i in l:
                    if (i['platform'] and i['direction']):
                        param_formatted_stop['next_departure'] = f"Platform {i['platform']} towards {i['direction']}"
                        found = True
                        params.remove("next_departure")
                        break
                if (found == False):
                    return {
                            "Error": 404,
                            "Message": f"Did not find any departures from {formatted_stop['stop_id']} within 120 mins",
                        }, 404

            # go through params list and add required fields
            for param in params:
                param_formatted_stop[param] = formatted_stop[param]
                pass

            return param_formatted_stop, 200
        
        


        # get next departure, duration is set to 120 mins max
        res = requests.get(f"https://v6.db.transport.rest/stops/{formatted_stop['stop_id']}/departures?duration=120")
        if (res.status_code == 503):
                    return {
                        "Error": 503,
                        "Message": "Service unavailable"
                    }
        l = res.json()
        l = l['departures']
        if (len(l) == 0):
            return {
                "Error": 404,
                "Message": f"Did not find any departures from {formatted_stop['stop_id']} within 120 mins",
            }, 404

        # iterate through list and find the first one where the platform and direction is not none
        found = False
        for i in l:
            if (i['platform'] and i['direction']):
                formatted_stop['next_departure'] = f"Platform {i['platform']} towards {i['direction']}"
                found = True
                break
        if (found == False):
                return {
                        "Error": 404,
                        "Message": f"Did not find any departures from {formatted_stop['stop_id']} within 120 mins",
                    }, 404
        

       
        return {
            "stop_id": formatted_stop['stop_id'],
            "last_updated": formatted_stop['last_updated'],
            "name": formatted_stop['name'],
            "latitude": formatted_stop['latitude'],
            "longitude": formatted_stop['longitude'],
            "next_departure": formatted_stop['next_departure'],
            "_links": {
                "self": {
                    "href": formatted_stop['self_link']
                },
                "next": {
                    "href": formatted_stop['next_link']
                },
                "prev": {
                    "href": formatted_stop['prev_link']
                }

            }
        }, 200
    
    @api.doc(responses={
        200: 'Success',
        400: 'Bad Request',
        404: 'Not Found',
    },
    description='Delete a given stop.')
    def delete(self, stop_id):
        # query database for the given stop_id
        # check if the given stop_id is contained within the database
        check_if_stop_exists = cursor.execute(f"SELECT stop_id FROM stops WHERE stop_id='{stop_id}'")
        check_if_stop_exists = check_if_stop_exists.fetchone()
        # the stop does not exist in the database, so 404 error
        if (not check_if_stop_exists):
            return {
                "message": f"The stop_id {stop_id} was not found in the database.",
                "stop_id": f"{stop_id}",
            }, 404
        # the stop exists in the database, so delete it
        cursor.execute(f"""DELETE FROM stops WHERE stop_id='{stop_id}'""")
        conn.commit()

        
        # update links of all the rows
        current_rows = []
        # Get all the table records of stops ordered by stop_id
        cursor.execute("SELECT * FROM stops ORDER BY stop_id")
        rows = cursor.fetchall()
        # convert the tuples that fetchall returns into dictionaries
        for row in rows:
            convert_row_to_dict = {
                "stop_id": row[0], # the first item should be a stop_id
                "name": row[1], # second item should be name of the stop
                "latitude": row[2], # third item should be latitude
                "longitude": row[3], # 4th item should be longitude
                "last_updated": row[4], # 5th item should be last_updated
                "self_link": row[5], # self link
                "prev_link": row[6], # prev link
                "next_link": row[7], # next link
            }
            current_rows.append(convert_row_to_dict)

        # iterate through the list of dictionaries
        # set prev_link to the row index before it
        # set the next_link to the row index after it
        # for the last dictionary set next_link to Null
        # for the first dictioanry set prev_link to Null
        for index, element in enumerate(current_rows):
            # for first item in the list, set the prev_link to Null
            if (index == 0 and len(current_rows) > 1):
                element['prev_link'] = None
                element['next_link'] = f"{current_rows[index+1]['self_link']}"
            elif (index == 0 and len(current_rows) == 1):
                # there is only stop in the db
                element['prev_link'] = None
                element['next_link'] = None
            elif (index + 1 < len(current_rows)):
                element['prev_link'] = f"{current_rows[index-1]['self_link']}"
                element['next_link'] = f"{current_rows[index+1]['self_link']}"
            elif (index == len(current_rows) - 1):
                element['prev_link'] = f"{current_rows[index-1]['self_link']}"
                element['next_link'] = None


            # update it in the db
            cursor.execute(f"""UPDATE stops SET next_link='{element['next_link']}' where stop_id='{element['stop_id']}'""")
            cursor.execute(f"""UPDATE stops SET prev_link='{element['prev_link']}' where stop_id='{element['stop_id']}'""")
            conn.commit()

        return {
            "message": f"The stop_id {stop_id} was removed from the database",
            "stop_id": f"{stop_id}",
        }, 200
    

   
    @api.doc(responses={
        200: 'Success',
        400: 'Bad Request',
        404: 'Not Found',
    },
    description='Updating a given stop.',
    body=api.model('Put Request Body', {
    }))
    def put(self, stop_id):
        # query database for the given stop_id
        # check if the given stop_id is contained within the database
        check_if_stop_exists = cursor.execute(f"SELECT stop_id FROM stops WHERE stop_id='{stop_id}'")
        check_if_stop_exists = check_if_stop_exists.fetchone()
        # the stop does not exist in the database, so 404 error
        if (not check_if_stop_exists):
            return {
                "message": f"The stop_id {stop_id} was not found in the database.",
                "stop_id": f"{stop_id}",
            }, 404
        
        # get the fields requested for updating
        payload = request.get_json()
        # list of allowable fields to be updated
        allowable_fields = ["name", "last_updated", "latitude", "longitude", "next_departure"]
        params =  {}
        for arg in payload:
            # check if the params are actually allowable fields to be updated
            if (arg not in allowable_fields):
                return {
                    "Error": 400,
                    "Message": f"{arg} is not a permissable field to be updated"
                }
            
            # check for last_updated field
            if (arg == "last_updated" and payload[arg] == ""):
                # if given empty string add it to params
                params[arg] = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

                continue
            elif (arg == "last_updated" and payload[arg] != ""):
                # verify that the string given complies with yyyy-mm-ddhh:mm:ss
                # https://www.geeksforgeeks.org/python-validate-string-date-format/
                res = True
                try:
                    res = bool(datetime.strptime(payload[arg], "%Y-%m-%d-%H:%M:%S"))
                except ValueError:
                    res = False
                # given correct format so add it to params dictionary to be updated
                if (res):
                    params[arg] = payload[arg] 
                else:
                # given incorrect format, so return 400 bad request
                    return {
                        "Error": 400,
                        "Message": f"Bad request, '{payload[arg]}' does not comply with datetime format of yyyy-mm-dd-hh:mm:ss"
                    }

            # get rid of param values that are empty strings
            if (payload[arg] != ""):
                params[arg] = payload[arg]
        
        # if no params provided
        if (not params):
            return {
                "Error": 400,
                "Message": "No fields provided to be updated"
            }


        # fields have been verified and 'params' dictionary holds values to be updated
        # so just go through the dictionary and update the fields in the database
        for param in params:
            cursor.execute(f"""UPDATE stops SET {param}='{params[param]}' WHERE stop_id='{stop_id}'""")
            conn.commit()

        # get info ready for return
        # check if the given stop_id is contained within the database
        updated_stop = cursor.execute(f"SELECT stop_id, last_updated, self_link FROM stops WHERE stop_id='{stop_id}'")
        updated_stop = updated_stop.fetchall()
        # the stop does not exist in the database, so 404 error
        if (not updated_stop):
            return {
                "Error Code": 404,
                "Message": f"The stop id of {stop_id} does not exist in the database"
            }, 404
        
        # The stop exists so format the data into a dictionary
        updated_stop_dict = {
            "stop_id": updated_stop[0][0],
            "last_updated": updated_stop[0][1],
            "self_link": updated_stop[0][2],
        }
        # return value
        ret = {
            "stop_id": updated_stop_dict['stop_id'],
            "last_updated": updated_stop_dict['last_updated'],
            "_links": {
                "self": {
                    "href": updated_stop_dict['self_link']
                }
            }
        }

        return ret

@api.route('/operator-profile/<int:stop_id>')
@api.doc(responses={
        200: 'Success',
        400: 'Bad Request',
        404: 'Not Found',
        503: 'Service unavailable'
    },
    description='Get a profile of each operator who is operating a service departing from desired stop within 90 mins',
    )
class Operator(Resource):
    def get(self, stop_id):
        # check if the given stop_id is contained within the database
        check_if_stop_exists = cursor.execute(f"SELECT stop_id FROM stops WHERE stop_id='{stop_id}'")
        check_if_stop_exists = check_if_stop_exists.fetchone()
        # the stop does not exist in the database, so 404 error
        if (not check_if_stop_exists):
            return {
                "message": f"The stop_id {stop_id} was not found in the database.",
                "stop_id": f"{stop_id}",
            }, 404

        # make api call with duration set to 90 mins max
        res = requests.get(f'https://v6.db.transport.rest/stops/{stop_id}/departures?duration=90')
        # if 503
        if (res.status_code == 503):
            return {
                "Error": 503,
                "Message": "Service unavailable",
            }, 503
        
        l = res.json()
        # isolate list of departures
        l = l['departures']

        # list of distinct operator names
        operators = []
        for item in l:
            # if the operator is not in the list, then add it in
            if (item['line']['operator']['name'] not in operators):
                operators.append(item['line']['operator']['name'])


        # return obj
        ret = {
            "stop_id": stop_id,
            "profiles": []
        }

        # for each of the unique operators
        for operator in operators:
            # make gemini call, ask gemini for info about operator
            question = f"Give me a summary of the operator {operator}"
            response = gemini.generate_content(question)
            
            # store response in dictionary
            operator_profile = {
                "operator_name": operator,
                "information": response.text,
            }

            # add it to profiles list in return dict
            ret['profiles'].append(operator_profile)

        return ret, 200

@api.route('/guide')
@api.doc(responses={
        200: 'Success',
        400: 'Bad Request',
        503: 'Service unavailable'
    },
    description='Returns a TXT file to help a tourist explore points of interest around a journey using stops from the database',
    )
class Operator(Resource):
    def get(self):
        # if the database has less than two stops in it, return error
        # check if the given stop_id is contained within the database
        at_least_two_stops = cursor.execute(f"SELECT * FROM stops ORDER BY stop_id")
        at_least_two_stops = at_least_two_stops.fetchall()
        # the stop does not exist in the database, so 404 error
        if (len(at_least_two_stops) < 2):
            return {
                "Error": 400,
                "message": f"There is less than two stops in the database, so cannot create a guide",
            }, 400
        
        # a list of just the stop_ids
        stop_ids = []
        for stop in at_least_two_stops:
            stop_ids.append(stop[0])

        # check if all stops in the database have a valid journey between them
        for source in stop_ids:
            for destination in stop_ids:
                # if the same stop_id in the list, skip this iteration
                if (source == destination):
                    continue
                
                # check all stops have a route between them
                routes = requests.get(f'https://v6.db.transport.rest/journeys?from={source}&to={destination}')
                
                if (routes.status_code == 503):
                    return {
                        "Error": 503,
                        "Message": "Service unavailable"
                    }

                routes = routes.json()

                if ('journeys' not in routes):
                    return {
                        "Error": 400,
                        "Message": "No journey"
                    }, 400

                # isolate journeys array to routes variable
                routes = routes['journeys']
                # if no journeys between source and destination
                if (len(routes) == 0):
                    return {
                        "Error": 400,
                        "Message": "No journey"
                    }, 400


        # if we made it to here, then that means no error was returned with all stops having a route/journey between them

        # spec says select any two stops in the database for information, I'm just picking the first two numerically by stop_id
        source_stop_id = stop_ids[0]
        dest_stop_id = stop_ids[1]

        # get latitude and longitude for source
        source_info = cursor.execute(f"SELECT stop_id, name, latitude, longitude FROM stops where stop_id='{source_stop_id}'")
        source_info = source_info.fetchall()
        
        # format source_info into dictionary
        source_info_dict = {
            "stop_id": source_info[0][0],
            "name": source_info[0][1],
            "latitude": source_info[0][2],
            "longitude": source_info[0][3],
        }

        # get latitude and longitude for source
        dest_info = cursor.execute(f"SELECT stop_id, name, latitude, longitude FROM stops where stop_id='{dest_stop_id}'")
        dest_info = dest_info.fetchall()
        
        # format source_info into dictionary
        dest_info_dict = {
            "stop_id": dest_info[0][0],
            "name": dest_info[0][1],
            "latitude": dest_info[0][2],
            "longitude": dest_info[0][3],
        }

        # make API call to db.transport for POI near source
        source_poi = requests.get(f"https://v6.db.transport.rest/locations/nearby?latitude={source_info_dict['latitude']}&longitude={source_info_dict['longitude']}&poi=true")

        # if 503
        if (source_poi.status_code == 503):
            return {
                "Error": 503,
                "Message": "Service unavailable"
            }
        
        source_poi = source_poi.json()
        
        poi_at_source = None
        # iterate through list and get location that has a 'poi' value of true
        for poi in source_poi:
            if (poi['type'] == 'location'):
                if (poi['poi'] == True):
                    poi_at_source = poi
                    break


        # make API call to db.transport for POI near source
        dest_poi = requests.get(f"https://v6.db.transport.rest/locations/nearby?latitude={dest_info_dict['latitude']}&longitude={dest_info_dict['longitude']}&poi=true")

        # if 503
        if (dest_poi.status_code == 503):
            return {
                "Error": 503,
                "Message": "Service unavailable"
            }
        
        dest_poi = dest_poi.json()
        
        poi_at_dest = None
        # iterate through list and get location that has a 'poi' value of true
        for poi in dest_poi:
            if (poi['type'] == 'location'):
                if (poi['poi'] == True):
                    poi_at_dest = poi
                    break

        # questions to ask gemini for the chosen POI's
        question_source_poi = f"Give me a summary of the POI {poi_at_source['name']}"
        question_dest_poi = f"Give me a summary of the POI {poi_at_dest['name']}"

        # responses from asking gemini about the respective POIs
        response_source = gemini.generate_content(question_source_poi)
        response_dest = gemini.generate_content(question_dest_poi)

        # additional info to enhance the experience of a tourist
        question_tourist_info = f"What advice would you give a tourist visiting the areas around {poi_at_source['name']} and {poi_at_dest['name']}? and any additional info you think is important"
        response_tourist_info = gemini.generate_content(question_tourist_info)

        # store the responses as text
        res_source = response_source.text
        res_dest = response_dest.text
        res_tourist = response_tourist_info.text

        all_text = "Source Info:\n" + res_source + "\n" + "\nDestination Info:\n" + res_dest + "\n" + 'Additional Tourist Info:\n' + res_tourist
        # write the info into a txt file
        f = open('z5390780.txt', "w")
        f.write(all_text)
        f.close()

        # send the file as part of the API
        send_file('z5390780.txt', download_name="z5390780.txt")
        return {}, 200


if __name__ == "__main__":
    # Here's a quick example of using the Generative AI API:
    #question = "Give me some facts about UNSW!"
    #response = gemini.generate_content(question)
    #print(question)
    #print(response.text)

    app.run(debug=True)