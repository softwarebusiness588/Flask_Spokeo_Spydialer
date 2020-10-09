'''This is the main flask python file'''
import time
from flask import Flask, redirect, render_template, request, send_from_directory, Response
import flask_progress_bar.flask_progress_bar as FPB
from Scraping.spokeo_release import SpokeoScraper
import os
import uuid
from werkzeug.utils import secure_filename
from flask import send_file

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT,'uploads')
INPUT_FILE = ""
def allowed_file(filename):
    """Check format of the file."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg', 'csv', 'png']


@app.route('/')
def index():
    '''This function redirects the user to the index page'''
    return render_template('index.html')

@app.route('/download')
def csv_file_download_with_file():
    file_name = "./Download/Output.xlsx"
    print("downloading...")
    return send_file(file_name,
                     attachment_filename='OutputResult.xlsx',
                     as_attachment=True)

@app.route('/upload', methods=['POST'])
def upload():
    """Upload file endpoint."""
    if request.method == 'POST':
        if not request.files.get('file', None):
            msg = 'the request contains no file'
            return render_template('exception.html', text=msg)

        file = request.files['file']
        if file and not allowed_file(file.filename):
            msg = f'the file {file.filename} has wrong extention'
            return render_template('exception.html', text=msg)
        
        if not os.path.isdir(UPLOAD_FOLDER):
            os.mkdir(UPLOAD_FOLDER)

        file.save(os.path.join(UPLOAD_FOLDER, secure_filename(file.filename)))

        return redirect('/process/' + file.filename)

@app.route('/completed')
def complete():
    '''This function redirects the user to the complete process  page'''
    return render_template('complete.html')

@app.route('/process/<filename>')
def task_processing(filename):
    """Process the image endpoint."""
    global INPUT_FILE
    INPUT_FILE = filename
    return render_template('processing.html', image_name=filename)

@app.route('/progress')
def progress():
    ''' 
    Function that return the ammount of photos taken for the progress bar 

    Follow this structure and replace the example_generator function with your own
    '''
    global INPUT_FILE
    params = {'input': 'input.csv', 'output': 'output.csv', 'max_count': 5, 'max_page_count': 0, 'config': 'config.ini', 'update': False, 'proxy': None}
    params['input'] = os.path.join(UPLOAD_FOLDER, secure_filename(INPUT_FILE))
    scraper = SpokeoScraper(params)
    scraper.login()
    
    # return Response(FPB.progress(example_generator()), mimetype='text/event-stream')
    return Response(FPB.progress(scraper.run()), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=False)
