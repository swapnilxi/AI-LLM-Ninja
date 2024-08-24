from flask import Flask, request, jsonify, render_template
import pandas as pd
from flask_cors import CORS, cross_origin
from flask_restful import Resource, Api


import logging
log_file = 'logs/logging.log'
logging.basicConfig(filename=log_file, encoding='utf-8', level=logging.DEBUG)

app = Flask(__name__)
CORS(app)
api = Api(app)

app.config['UPLOAD_FOLDER'] = "data/"


class PredictRul(Resource):
    '''Class with Post method for report generation.'''
    @cross_origin()
    def post(self):
        try:
            file = request.files['file']

            pred = pd.DataFrame({
            "Engine ID": [2,5,10,18],
            "Predicted Engine Life": ["48 Cycles","43 Cycles","2 Cycles","28 Cycles"],
            "Engine Status": ["Healthy 🟢","Healthy 🟢","Repair 🔴","Caution 🟡"]
            })

            predictions = pred.to_dict(orient='records')
            
            return jsonify({"rul_predictions":predictions, "avg_rul":30.25, "total_assets":7, "in_use":4, "retired":3, "Success":0})
    
        except Exception as ee:
            print("Error: ", str(ee))
            logging.error(str(ee))
            return {'Success': 1, 'Resp': str(ee)}   

class Filter(Resource):
    @cross_origin()
    def post(self):
        try:
            engine_id = request.form.get("engine_id")
            return {"user choice": f"{engine_id}"}

        except Exception as ee:
            print("Error: ", str(ee))
            logging.error(str(ee))
            return {'Success': 1, 'Resp': str(ee)}


class Schedule(Resource):
    @cross_origin()
    def post(self):
        try:
            invent = pd.DataFrame({
                "Inventory ID":["TK1","TK2","TK3"],
                "Part Name":["Bearing","Gasket","Seal"],
                "Quantity Needed to Repair Engine":[20,34,73],
                "Location":["101-A","102-A","103-A"],
                "Availability":[
                    [{"date":"01-07", "quantity":10},{"date":"02-07", "quantity":5},{"date":"03-07", "quantity":15}],
                    [{"date":"01-07", "quantity":3},{"date":"02-07", "quantity":6},{"date":"03-07", "quantity":10}],
                    [{"date":"01-07", "quantity":20},{"date":"02-07", "quantity":26},{"date":"03-07", "quantity":35}]
                ]
            })

            staff = pd.DataFrame({
                "Staff ID":["ST1","ST2","ST3"],
                "Staff Name":["Maxi","David","John"],
                "Skills":["Engine Assembly","Component Inspection","Welding"],
                "Location":["101-A","102-A","103-A"],
                "Availability":[
                    [{"date":"01-07", "status":"Not Available"},{"date":"02-07", "status":"Available"},{"date":"03-07", "status":"Available"}],
                    [{"date":"01-07", "status":"Available"},{"date":"02-07", "status":"Available"},{"date":"03-07", "status":"Not Available"}],
                    [{"date":"01-07", "status":"Available"},{"date":"02-07", "status":"Available"},{"date":"03-07", "status":"Available"}]
                ]
            })

            inventory = invent.to_dict(orient='records')
            staff = staff.to_dict(orient='records')
            return jsonify({"inventory":inventory, "staff":staff, "Success":0})
        
        except Exception as ee:
            print("Error: ", str(ee))
            logging.error(str(ee))
            return {'Success': 1, 'Resp': str(ee)}   



class ChatDB(Resource):
    '''Class with Post method for report generation.'''
    @cross_origin()
    def post(self):
        try:            
            query = request.form.get("query","how many engines with less than 30 cycles of RUL")
            resp = "Here are the days you can repair Engine 5"
            dates = "20-07-2024, 21-07-2024, 23-07-2024"
            #resp = respond_to_query(query)
            return {"response":resp, "dates":dates, "Success":0}
        except Exception as ee:
            print("Error: ", str(ee))
            logging.error(str(ee))
            return {'Success': 1, 'Resp': str(ee)}       


class ResponseCheck(Resource):
    '''Check working status of flask app.'''
    @cross_origin()
    def get(self):
        """
        This functions checks whether the flask app is working
        """
        response = jsonify({"Working Fine": 0})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.status_code = 200
        logging.info("Status Check")
        return response

api.add_resource(ResponseCheck, "/")
api.add_resource(PredictRul,"/rul")
api.add_resource(Schedule,"/sched")
api.add_resource(Filter,"/filter")
api.add_resource(ChatDB,"/chat")

if __name__ == "__main__":
    # start flask app
    app.run(debug=True)