from flask import Flask, render_template, request, send_file, redirect, send_from_directory, url_for, jsonify
import rasterio
import numpy as np
from PIL import Image
import io
import base64
import os
import tempfile
from osgeo import gdal

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'tif', 'tiff'}

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_bathymetry_image(file_path, north, south, east, west):
    try:
        with rasterio.open(file_path) as dataset:
            print(f"Dataset bounds: {dataset.bounds}")
            print(f"Input coordinates: North={north}, South={south}, East={east}, West={west}")

            window = rasterio.windows.from_bounds(west, south, east, north, dataset.transform)
            data = dataset.read(1, window=window)

            if data.size == 0:
                print("No data found in the selected bounding box.")
                return None

            normalized_data = np.interp(data, (data.min(), data.max()), (0, 255)).astype(np.uint8)
            img = Image.fromarray(normalized_data)
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            return base64.b64encode(img_bytes.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"An error occurred while processing the TIFF file: {e}")
        return None

def save_cropped_tiff(file_path, north, south, east, west):
    try:
        with rasterio.open(file_path) as dataset:
            window = rasterio.windows.from_bounds(west, south, east, north, dataset.transform)
            data = dataset.read(1, window=window)

            if data.size == 0:
                return None

            metadata = dataset.meta.copy()
            metadata.update({
                'height': window.height,
                'width': window.width,
                'transform': dataset.window_transform(window)
            })

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tif')
            with rasterio.open(temp_file.name, 'w', **metadata) as dst:
                dst.write(data, 1)

            return temp_file.name
    except Exception as e:
        print(f"An error occurred while saving the cropped TIFF file: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            north = float(request.form['north'])
            south = float(request.form['south'])
            east = float(request.form['east'])
            west = float(request.form['west'])

            # Use the global TIFF file path
            file_path = r"C:\SIH-2024\your_project_directory\your_project_directory\datasetss.tif"
            img_data = get_bathymetry_image(file_path, north, south, east, west)
            if img_data:
                return render_template('index.html', image_data=img_data, file_path=file_path, north=north, south=south, east=east, west=west)
            else:
                return render_template('index.html', error="No data found for the specified bounding box.")
        except ValueError:
            return render_template('index.html', error="Invalid input. Please enter valid numeric values.")
        except Exception as e:
            print(f"An error occurred in the index route: {e}")
            return render_template('index.html', error="An unexpected error occurred.")
    
    return render_template('index.html')

@app.route('/download_tiff', methods=['POST'])
def download_tiff():
    try:
        file_path = request.form['file_path']
        north = float(request.form['north'])
        south = float(request.form['south'])
        east = float(request.form['east'])
        west = float(request.form['west'])
        
        cropped_tiff_path = save_cropped_tiff(file_path, north, south, east, west)
        if cropped_tiff_path:
            return send_file(cropped_tiff_path, as_attachment=True)
        else:
            return redirect(url_for('index', error="An error occurred while creating the TIFF file."))
    except Exception as e:
        print(f"An error occurred while downloading the TIFF file: {e}")
        return redirect(url_for('index', error="An error occurred while processing the TIFF file."))

@app.route('/download_cog', methods=['GET'])
def download_cog():
    file_path = request.args.get('file_path')
    north = float(request.args.get('north'))
    south = float(request.args.get('south'))
    east = float(request.args.get('east'))
    west = float(request.args.get('west'))

    try:
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_file:
            temp_file_path = temp_file.name

        # Use GDAL to create a COG
        gdal.Translate(temp_file_path, file_path, projWin=[west, north, east, south], format='COG')

        return send_file(temp_file_path, as_attachment=True, download_name='cog_data.tif')

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/process_tiff', methods=['GET', 'POST'])
def process_tiff():
    if request.method == 'POST':
        file = request.files.get('tiffFile')
        if file and allowed_file(file.filename):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            return render_template('process_tiff.html', file_path=file_path)
        else:
            return render_template('process_tiff.html', error="Invalid file format or no file uploaded.")
    return render_template('process_tiff.html')

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=5001)