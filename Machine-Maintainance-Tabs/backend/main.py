from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_restful import Resource, Api
import logging

log_file = 'logs/logging.log'
logging.basicConfig(filename=log_file, encoding='utf-8', level=logging.DEBUG)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})  
api = Api(app)

app.config['UPLOAD_FOLDER'] = "data/"

class Schedule(Resource):
    '''Class with Post method for report generation.'''
    @cross_origin()
    def post(self):
        try:
            location = request.json.get('location', '')
            inventory = [
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 2},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 8},
                        {"date": "04/07/2023", "quantity": 8},
                        {"date": "05/07/2023", "quantity": 4},
                        {"date": "06/07/2023", "quantity": 3},
                        {"date": "07/07/2023", "quantity": 3}
                    ],
                    "inventory_id": "HSS103",
                    "part_required": "Shims and spacers",
                    "quantity_required": 4
                },
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 8},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 2},
                        {"date": "04/07/2023", "quantity": 6},
                        {"date": "05/07/2023", "quantity": 6},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 1}
                    ],
                    "inventory_id": "HSL21",
                    "part_required": "Seal",
                    "quantity_required": 3
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 8},
                        {"date": "02/07/2023", "quantity": 9},
                        {"date": "03/07/2023", "quantity": 2},
                        {"date": "04/07/2023", "quantity": 8},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 6},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "inventory_id": "TRGT52",
                    "part_required": "Gasket",
                    "quantity_required": 1
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 1},
                        {"date": "02/07/2023", "quantity": 8},
                        {"date": "03/07/2023", "quantity": 1},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 2},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "inventory_id": "HGT52",
                    "part_required": "Gasket",
                    "quantity_required": 2
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 4},
                        {"date": "02/07/2023", "quantity": 9},
                        {"date": "03/07/2023", "quantity": 6},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 4},
                        {"date": "06/07/2023", "quantity": 9},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "inventory_id": "BRET52",
                    "part_required": "Engine Hoist",
                    "quantity_required": 4
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 9},
                        {"date": "02/07/2023", "quantity": 2},
                        {"date": "03/07/2023", "quantity": 9},
                        {"date": "04/07/2023", "quantity": 5},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 5},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "inventory_id": "HSS52",
                    "part_required": "Shims and spacers",
                    "quantity_required": 1
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 1},
                        {"date": "02/07/2023", "quantity": 2},
                        {"date": "03/07/2023", "quantity": 2},
                        {"date": "04/07/2023", "quantity": 1},
                        {"date": "05/07/2023", "quantity": 3},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "inventory_id": "LSL52",
                    "part_required": "Seal",
                    "quantity_required": 3
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 8},
                        {"date": "02/07/2023", "quantity": 3},
                        {"date": "03/07/2023", "quantity": 4},
                        {"date": "04/07/2023", "quantity": 8},
                        {"date": "05/07/2023", "quantity": 3},
                        {"date": "06/07/2023", "quantity": 6},
                        {"date": "07/07/2023", "quantity": 1}
                    ],
                    "inventory_id": "TRGT103",
                    "part_required": "Gasket",
                    "quantity_required": 3
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 5},
                        {"date": "02/07/2023", "quantity": 1},
                        {"date": "03/07/2023", "quantity": 1},
                        {"date": "04/07/2023", "quantity": 8},
                        {"date": "05/07/2023", "quantity": 9},
                        {"date": "06/07/2023", "quantity": 5},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "inventory_id": "PEGT103",
                    "part_required": "Gasket",
                    "quantity_required": 1
                },
                {
                    "asset_location": "110-C",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 9},
                        {"date": "02/07/2023", "quantity": 5},
                        {"date": "03/07/2023", "quantity": 7},
                        {"date": "04/07/2023", "quantity": 8},
                        {"date": "05/07/2023", "quantity": 2},
                        {"date": "06/07/2023", "quantity": 4},
                        {"date": "07/07/2023", "quantity": 3}
                    ],
                    "inventory_id": "TRGT184",
                    "part_required": "Gasket",
                    "quantity_required": 4
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 6},
                        {"date": "02/07/2023", "quantity": 3},
                        {"date": "03/07/2023", "quantity": 5},
                        {"date": "04/07/2023", "quantity": 2},
                        {"date": "05/07/2023", "quantity": 2},
                        {"date": "06/07/2023", "quantity": 5},
                        {"date": "07/07/2023", "quantity": 7}
                    ],
                    "inventory_id": "HGT103",
                    "part_required": "Gasket",
                    "quantity_required": 3
                },
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 5},
                        {"date": "02/07/2023", "quantity": 5},
                        {"date": "03/07/2023", "quantity": 7},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 3},
                        {"date": "07/07/2023", "quantity": 5}
                    ],
                    "inventory_id": "HBG21",
                    "part_required": "Bearing",
                    "quantity_required": 1
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 4},
                        {"date": "02/07/2023", "quantity": 1},
                        {"date": "03/07/2023", "quantity": 5},
                        {"date": "04/07/2023", "quantity": 6},
                        {"date": "05/07/2023", "quantity": 3},
                        {"date": "06/07/2023", "quantity": 5},
                        {"date": "07/07/2023", "quantity": 9}
                    ],
                    "inventory_id": "LSL103",
                    "part_required": "Seal",
                    "quantity_required": 1
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 2},
                        {"date": "02/07/2023", "quantity": 1},
                        {"date": "03/07/2023", "quantity": 8},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 8},
                        {"date": "07/07/2023", "quantity": 9}
                    ],
                    "inventory_id": "HSL103",
                    "part_required": "Seal",
                    "quantity_required": 1
                },
                {
                    "asset_location": "110-C",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 1},
                        {"date": "02/07/2023", "quantity": 3},
                        {"date": "03/07/2023", "quantity": 8},
                        {"date": "04/07/2023", "quantity": 8},
                        {"date": "05/07/2023", "quantity": 5},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 6}
                    ],
                    "inventory_id": "HSL184",
                    "part_required": "Seal",
                    "quantity_required": 4
                }
            ]

            staff = [
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 4},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 3},
                        {"date": "04/07/2023", "quantity": 1},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 4},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "crew_required": 4,
                    "skill": "Precision Fitting"
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 3},
                        {"date": "02/07/2023", "quantity": 2},
                        {"date": "03/07/2023", "quantity": 2},
                        {"date": "04/07/2023", "quantity": 2},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 4},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "crew_required": 1,
                    "skill": "Calibration"
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 2},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 4},
                        {"date": "04/07/2023", "quantity": 3},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 1},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "crew_required": 1,
                    "skill": "Blade Balancing"
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 3},
                        {"date": "02/07/2023", "quantity": 3},
                        {"date": "03/07/2023", "quantity": 4},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 3}
                    ],
                    "crew_required": 3,
                    "skill": "Calibration"
                },
                {
                    "asset_location": "110-C",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 4},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 4},
                        {"date": "04/07/2023", "quantity": 1},
                        {"date": "05/07/2023", "quantity": 4},
                        {"date": "06/07/2023", "quantity": 3},
                        {"date": "07/07/2023", "quantity": 1}
                    ],
                    "crew_required": 1,
                    "skill": "Rigging Techniques"
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 3},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 2},
                        {"date": "04/07/2023", "quantity": 1},
                        {"date": "05/07/2023", "quantity": 4},
                        {"date": "06/07/2023", "quantity": 4},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "crew_required": 4,
                    "skill": "Load Balancing"
                },
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 4},
                        {"date": "02/07/2023", "quantity": 1},
                        {"date": "03/07/2023", "quantity": 1},
                        {"date": "04/07/2023", "quantity": 1},
                        {"date": "05/07/2023", "quantity": 3},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "crew_required": 1,
                    "skill": "Calibration"
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 3},
                        {"date": "02/07/2023", "quantity": 2},
                        {"date": "03/07/2023", "quantity": 4},
                        {"date": "04/07/2023", "quantity": 3},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "crew_required": 1,
                    "skill": "Precision Fitting"
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 1},
                        {"date": "02/07/2023", "quantity": 1},
                        {"date": "03/07/2023", "quantity": 4},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 4},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "crew_required": 1,
                    "skill": "Precision Fitting"
                },
                {
                    "asset_location": "120-B",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 2},
                        {"date": "02/07/2023", "quantity": 3},
                        {"date": "03/07/2023", "quantity": 3},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 4},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "crew_required": 3,
                    "skill": "Thread Repair"
                },
                {
                    "asset_location": "101-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 4},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 3},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 3},
                        {"date": "06/07/2023", "quantity": 1},
                        {"date": "07/07/2023", "quantity": 4}
                    ],
                    "crew_required": 3,
                    "skill": "Seal Installation"
                },
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 2},
                        {"date": "02/07/2023", "quantity": 3},
                        {"date": "03/07/2023", "quantity": 1},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 3},
                        {"date": "07/07/2023", "quantity": 3}
                    ],
                    "crew_required": 1,
                    "skill": "Thread Repair"
                },
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 1},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 3},
                        {"date": "04/07/2023", "quantity": 2},
                        {"date": "05/07/2023", "quantity": 1},
                        {"date": "06/07/2023", "quantity": 1},
                        {"date": "07/07/2023", "quantity": 2}
                    ],
                    "crew_required": 2,
                    "skill": "Load Balancing"
                },
                {
                    "asset_location": "201-A",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 3},
                        {"date": "02/07/2023", "quantity": 2},
                        {"date": "03/07/2023", "quantity": 1},
                        {"date": "04/07/2023", "quantity": 2},
                        {"date": "05/07/2023", "quantity": 3},
                        {"date": "06/07/2023", "quantity": 2},
                        {"date": "07/07/2023", "quantity": 3}
                    ],
                    "crew_required": 2,
                    "skill": "Seal Installation"
                },
                {
                    "asset_location": "110-C",
                    "availability": [
                        {"date": "01/07/2023", "quantity": 2},
                        {"date": "02/07/2023", "quantity": 4},
                        {"date": "03/07/2023", "quantity": 1},
                        {"date": "04/07/2023", "quantity": 4},
                        {"date": "05/07/2023", "quantity": 4},
                        {"date": "06/07/2023", "quantity": 4},
                        {"date": "07/07/2023", "quantity": 1}
                    ],
                    "crew_required": 2,
                    "skill": "Fault Diagnosis"
                }
            ]

            kpis = [
                {
                    "avg_rul": "30.25",
                    "in_use": "4",
                    "retired": "3",
                    "total_assets": "7"
                }
            ]

            rul_predictions = [
                {
                    "engine_id": "TK2",
                    "engine_status": "Healthy",
                    "pred_rul": "48 Cycles"
                },
                {
                    "engine_id": "TK5",
                    "engine_status": "Healthy",
                    "pred_rul": "43 Cycles"
                },
                {
                    "engine_id": "TK10",
                    "engine_status": "Repair",
                    "pred_rul": "2 Cycles"
                },
                {
                    "engine_id": "TK18",
                    "engine_status": "Caution",
                    "pred_rul": "28 Cycles"
                }
            ]

            filtered_inventory = [item for item in inventory if item['asset_location'] == location]
            filtered_staff = [item for item in staff if item['asset_location'] == location]

            response = jsonify({
                "inventory": filtered_inventory,
                "staff": filtered_staff,
                "Success": 0
            })
            response.status_code = 200
            return response

        except Exception as ee:
            print("Error: ", str(ee))
            logging.error(str(ee))
            response = jsonify({'Success': 1, 'Resp': str(ee)})
            response.status_code = 500  
            return response

class ResponseCheck(Resource):
    '''Check working status of flask app.'''
    @cross_origin()
    def get(self):
        response = jsonify({"Working Fine": 0})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.status_code = 200
        logging.info("Status Check")
        return response

api.add_resource(ResponseCheck, "/")
api.add_resource(Schedule, "/sched")

if __name__ == "__main__":
    app.run(debug=True)
