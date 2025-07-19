from utils.base_order_rate_simulation import get_base_order_rate
from utils.area_data_simulation_bounding_box import get_cumulative_order_rate
from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.graph import G
import logging
import gc
import psutil
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route("/health", methods=["GET"])
def health():
    try:

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()
        

        if cpu_percent > 90:
            return jsonify(
                status="degraded", 
                reason="High CPU usage",
                cpu_percent=cpu_percent,
                memory_percent=memory_info.percent
            ), 503
            
        if memory_info.percent > 90:
            return jsonify(
                status="degraded", 
                reason="High memory usage",
                cpu_percent=cpu_percent,
                memory_percent=memory_info.percent
            ), 503
        

        test_base_id = list(get_base_order_rate.__globals__.get('base_order_rate', {}).keys())
        if not test_base_id:
            return jsonify(status="fail", reason="No base data available"), 500
            
        return jsonify(
            status="ok",
            cpu_percent=cpu_percent,
            memory_percent=memory_info.percent,
            available_bases=len(test_base_id)
        ), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify(status="fail", reason=str(e)), 500

@app.route('/get_base_order_rate', methods=['POST'])
def get_base_order_rate_route():
    
    try:
        data = request.get_json(silent=True) or {}
        base_id = data.get('base_id')
        base_id = str(base_id)
        
        if not base_id:
            return jsonify({"error": "Missing base_id parameter."}), 400
            
        rate = get_base_order_rate(base_id)
        if rate is None:
            return jsonify({"error": "Base ID not found."}), 404
            
        return jsonify({"base_order_rate": rate})
        
    except Exception as e:
        logger.error(f"Error in get_base_order_rate: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_cumulative_order_rate', methods=['POST'])
def get_cumulative_order_rate_route():
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        coord_awal = tuple(data.get('coordAwal', []))
        coord_akhir = tuple(data.get('coordAkhir', []))
        
        if len(coord_awal) != 2 or len(coord_akhir) != 2:
            return jsonify({"error": "Invalid coordinate format. Expecting [lat, lon] arrays."}), 400
            
        result = get_cumulative_order_rate(coord_awal, coord_akhir, G)
        return jsonify({"cumulative_order_rate": result})
        
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Input validation error: {str(e)}")
        return jsonify({"error": "Invalid input format. Expecting coordAwal and coordAkhir lists."}), 400
    except Exception as e:
        logger.error(f"Error in get_cumulative_order_rate: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_cumulative_order_rate_matrix', methods=['POST'])
def get_cumulative_order_rate_matrix_route():
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        source_coords = data.get('source_coords', [])
        destination_coords = data.get('destination_coords', [])
        

        if not isinstance(source_coords, list) or not isinstance(destination_coords, list):
            return jsonify({"error": "source_coords and destination_coords must be lists"}), 400
        
        if len(source_coords) == 0 or len(destination_coords) == 0:
            return jsonify({"error": "Coordinate lists cannot be empty"}), 400
            
        

        source_coords = [tuple(coord) for coord in source_coords]
        destination_coords = [tuple(coord) for coord in destination_coords]
        

        matrix = []
        total_calculations = len(source_coords) * len(destination_coords)
        completed = 0
        
        for i, source_coord in enumerate(source_coords):
            row = []
            for j, dest_coord in enumerate(destination_coords):
                try:
                    result = get_cumulative_order_rate(source_coord, dest_coord, G)
                    row.append(result)
                    completed += 1
                    

                    if total_calculations > 10 and completed % 10 == 0:
                        logger.info(f"Matrix calculation progress: {completed}/{total_calculations}")
                        
                except Exception as e:
                    logger.error(f"Error calculating route from {source_coord} to {dest_coord}: {str(e)}")
                    row.append(None)
                    
            matrix.append(row)
        
        return jsonify({
            "cumulative_order_rate_matrix": matrix,
            "source_coords": source_coords,
            "destination_coords": destination_coords,
            "matrix_dimensions": {
                "rows": len(source_coords),
                "columns": len(destination_coords)
            },
            "successful_calculations": sum(1 for row in matrix for cell in row if cell is not None)
        })
        
    except Exception as e:
        logger.error(f"Error in get_cumulative_order_rate_matrix: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_vector_base_order_rate', methods=['POST'])
def get_vector_base_order_rate_route():
    
    try:
        data = request.get_json(silent=True) or {}
        base_ids = data.get('base_ids', [])
        base_ids = [str(i) for i in base_ids]
        
        if not base_ids:
            return jsonify({"error": "Missing base_ids parameter."}), 400
        
        if not isinstance(base_ids, list):
            return jsonify({"error": "base_ids must be a list."}), 400
        
        if len(base_ids) == 0:
            return jsonify({"error": "base_ids cannot be empty."}), 400
            

        if len(base_ids) > 1000:
            return jsonify({"error": "Too many base_ids. Maximum 1000 allowed."}), 400
        

        base_order_rates = []
        not_found_ids = []
        
        for base_id in base_ids:
            rate = get_base_order_rate(base_id)
            if rate is None:
                not_found_ids.append(base_id)
                base_order_rates.append(None)
            else:
                base_order_rates.append(rate)
        
        response = {
            "base_order_rates": base_order_rates,
            "base_ids": base_ids,
            "total_requested": len(base_ids),
            "successful_retrievals": len([rate for rate in base_order_rates if rate is not None])
        }
        
        if not_found_ids:
            response["not_found_base_ids"] = not_found_ids
            response["warning"] = f"{len(not_found_ids)} base ID(s) not found"
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_vector_base_order_rate: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    

    if hasattr(app, '_request_count'):
        app._request_count += 1
    else:
        app._request_count = 1
        
    if app._request_count % 100 == 0:
        gc.collect()
        
    return response

if __name__ == '__main__':
    app.run(
        host='0.0.0.0', 
        port=5002, 
        debug=False,
        use_reloader=False,
        threaded=True
    )
