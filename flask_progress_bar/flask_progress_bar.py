import json
def progress(generator):  
    ''' Generator that takes the progress data into the bar'''
    percent = 0
    while percent < 100:
        progress_data = generator
        for data in progress_data:
            percent_spokeo = round(((float(data[0])) * 100) / float(data[1]))
            percent_spydialer = round(((float(data[2])) * 100) / float(data[3]))
            res = {"percent_spokeo": str(percent_spokeo), "percent_spydialer": str(percent_spydialer), "info": data[4]}
            yield "data:" + str(json.dumps(res)) + "\n\n"

    # yield "data:100\n\n" # in case percentage fails
    tempRes = {"percent": 100, "info": "processing"}
    yield "data:" + str(json.dumps(tempRes)) + "\n\n"


