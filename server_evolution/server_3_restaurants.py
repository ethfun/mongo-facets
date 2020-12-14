from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__, static_folder='../client')
client = MongoClient(host="localhost", port=27017)
db_auth = client.admin
db_auth.authenticate("admin", "secret")
db = client.opendata
API_ENDPOINT = '/api/v1'

def _get_array_param(param):
    return filter(None, param.split(","))

# API
@app.route(API_ENDPOINT + "/restaurants")
def restaurants():
    # pagination
    page = int(request.args.get('page', '0'))
    page_size = int(request.args.get('page-size', '50'))
    skip = page * page_size
    limit = min(page_size, 50)

    # filters
    search = request.args.get('search', '')
    brands = _get_array_param(request.args.get('boroughs', ''))
    primary_category_ids = _get_array_param(request.args.get('cuisines', ''))
    secondary_category_ids = _get_array_param(request.args.get('zipcodes', ''))

    find = {}
    if search:
        find['$text'] = {'$search': search}
    if brands:
        # boroughs
        find['data.brand_alpha'] = {'$in': brands}
    if primary_category_ids:
        # cuisines
        find['data.primary_category_id'] = {'$in': primary_category_ids}
    if secondary_category_ids:
        # address.zipcode
        find['data.secondary_category_id'] = {'$in': secondary_category_ids}

    response = {
        'restaurants': list(db.product.find(find).skip(skip).limit(limit)),
        'count': db.product.find(find).count()
    }

    for restaurant in response['restaurants']:  # remove _id, is an ObjectId and is not serializable
        del restaurant['_id']
    return jsonify(response)

# Statics
@app.route('/')
def root():
  return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_proxy(path):
  # send_static_file will guess the correct MIME type
  return app.send_static_file(path)

# run the application without flask-cli
if __name__ == "__main__":
    app.run(debug=True)