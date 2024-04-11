import logging
import azure.functions as func
import json, base64, sys, os
from uuid import uuid4
from azure.storage.blob import BlobClient, ContentSettings

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="imagesegment")
def imagesegment(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        body = json.dumps(req.get_json())
    except ValueError:
        return func.HttpResponse(
            "Invalid body",
            status_code=400
        )
    
    if body:
        result = compose_response(body)
        return func.HttpResponse(result, mimetype="application/json")
    else:
        return func.HttpResponse(
            "Invalid body",
            status_code=400
        )


def compose_response(json_data):
    values = json.loads(json_data)['values']
    
    # Prepare the Output before the loop
    results = {}
    results["values"] = []
    
    for value in values:
        output_record = transform_value(value)
        if output_record != None:
            results["values"].append(output_record)
    return json.dumps(results, ensure_ascii=False)

## Perform an operation on a record
def transform_value(value):
    try:
        recordId = value['recordId']
    except AssertionError  as error:
        return None

    # Validate the inputs
    try:         
        assert ('data' in value), "'data' field is required."
        data = value['data']        
    except AssertionError  as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "Error:" + error.args[0] }   ]       
            })

    try:                
        # Here you could do something more interesting with the inputs 
        images = list(map(lambda x: get_image(x), data['images']))
        output = list(map(lambda x: write_on_blob_storage2(x), images))
        output = list(map(lambda x: format_to_acs(x), output))
            
    except ValueError  as error:
        logging.info(f"Unexpected error: {sys.exc_info()[0]}  - {error.args[0]}")
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": f"Could not complete operation for record. {error.args[0]}" }   ]       
            })

    return ({
            "recordId": recordId,
            "data": {
                "normalized_images_merged": output
                    }
            })


def format_to_acs(data):
    return {
        "$type" : "file",
        "contentType": "image/jpeg",
        "data" : data['base64String'],
        "height" : data['height'],
        "width" : data['width'],
        "pageNumber" : data['pageNumber'],
        "image_url" : data['image_url']
    }
    

def get_image(data):
    result = {
        "data" : None,
        "originalWidth" : data['originalWidth'],
        "originalHeight": data['originalHeight'],
        "pageNumber" : data['pageNumber'],
        "contentOffset" : data['contentOffset']
    }
    base64String = data['data']
    base64Bytes = base64String.encode('utf-8')
    inputBytes = base64.b64decode(base64Bytes)

    result['image_to_store'] = inputBytes
    result['base64String'] = base64String
    result['height'] = data['originalHeight']
    result['width'] = data['originalWidth']
    result['pageNumber'] = data['pageNumber']
    return result

def write_on_blob_storage2(data):
    # data_bytes = data['base64Bytes']
    data_bytes = data['image_to_store']
    conn_str = os.getenv('blob_storage_connection_string', None)
    container_name = os.getenv('blob_storage_container', None)
    blob_name = f"{uuid4()}.jpeg"
    if conn_str and container_name:
        # Create full Blob URL
        x = conn_str.split(';')
        image_url = f"{x[0].split('=')[1]}://{x[1].split('=')[1]}.{x[3].split('=')[1]}/{container_name}/{blob_name}"
        data['image_url'] = image_url
        # Upload data on Blob
        blob_client = BlobClient.from_connection_string(conn_str=conn_str, container_name=container_name, blob_name=blob_name)
        content_settings = ContentSettings(content_type='image/jpeg')
        blob_client.upload_blob(data_bytes, content_settings=content_settings)
        return data