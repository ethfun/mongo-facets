from flask import Flask, request, jsonify
from pymongo import MongoClient


app = Flask(__name__, static_folder='client')
# PRO
client = MongoClient(host="localhost", port=27017)
db_auth = client.admin
db_auth.authenticate("admin", "secret")
db = client.opendata
API_ENDPOINT = '/api/v1'


# @TODO 再加一个Source过滤 secoo/aplum/sheku/xinshang/xbiao/

def _get_array_param(param):
    return list(filter(None, param.split(",")))


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

    match = {}
    if search:
        match['$text'] = {'$search': search}
    if brands:
        # boroughs
        match['data.brand_alpha'] = {'$in': brands}
    if primary_category_ids:
        # cuisines
        match['data.primary_category_id'] = {'$in': primary_category_ids}
    if secondary_category_ids:
        # address.zipcode
        match['data.secondary_category_id'] = {'$in': secondary_category_ids}

    pipeline = [{
        '$match': match
    }] if match else []

    pipeline += [{
        '$facet': {
            'restaurants': [
                {'$skip': skip},
                {'$limit': limit}
            ],
            'count': [
                {'$count': 'total'}
            ],
        }
    }]

    # print(list(db.product.aggregate(pipeline)))
    result = list(db.product.aggregate(pipeline))[0]

    for restaurant in result['restaurants']: # remove _id, is an ObjectId and is not serializable
        del restaurant['_id']
    result['count'] = result['count'][0]['total'] if result['count'] else 0
    return jsonify(result)


@app.route(API_ENDPOINT + "/restaurants/facets")
def restaurant_facets():
    # filters
    search = request.args.get('search', '')
    # boroughs = _get_array_param(request.args.get('boroughs', ''))
    # cuisines = _get_array_param(request.args.get('cuisines', ''))
    # zipcodes = _get_array_param(request.args.get('zipcodes', ''))
    brands = _get_array_param(request.args.get('boroughs', ''))
    primary_category_ids = _get_array_param(request.args.get('cuisines', ''))
    secondary_category_ids = _get_array_param(request.args.get('zipcodes', ''))

    pipeline = [{
        '$match': {'$text': {'$search': search}}
    }] if search else []

    pipeline += [{
        '$facet': {
            'brands': _get_facet_brand_pipeline(primary_category_ids, secondary_category_ids),
            'primaryCategoryIds': _get_facet_primary_category_pipeline(brands, secondary_category_ids),
            'secondaryCategoryId': _get_facet_secondary_category_pipeline(brands, primary_category_ids),
        }
    }]

    product_facets = list(db.product.aggregate(pipeline))[0]

    return jsonify(product_facets)


def _get_facet_brand_pipeline(primary_category_ids, secondary_category_ids):
    match = {}

    if primary_category_ids:
        match['data.primary_category_id'] = {'$in': primary_category_ids}
    if secondary_category_ids:
        match['data.secondary_category_id'] = {'$in': secondary_category_ids}

    pipeline = [
        {'$match': match}
    ] if match else []

    # return pipeline + _get_group_pipeline('borough')
    return pipeline + _get_group_pipeline('data.brand_alpha')


def _get_facet_primary_category_pipeline(brands, secondary_category_ids):
    match = {}

    if brands:
        match['data.brand_alpha'] = {'$in': brands}
    if secondary_category_ids:
        match['data.secondary_category_id'] = {'$in': secondary_category_ids}

    pipeline = [
        {'$match': match}
    ] if match else []

    # return pipeline + _get_group_pipeline('cuisine')
    return pipeline + _get_group_pipeline('data.primary_category_id')


def _get_facet_secondary_category_pipeline(brands, primary_category_ids):
    match = {}

    if brands:
        # match['borough'] = {'$in': boroughs}
        match['data.brand_alpha'] = {'$in': brands}
    if primary_category_ids:
        # match['cuisine'] = {'$in': cuisines}
        match['data.primary_category_id'] = {'$in': primary_category_ids}

    pipeline = [
        {'$match': match},
    ] if match else []

    # return pipeline + _get_group_pipeline('address.zipcode')
    return pipeline + _get_group_pipeline('data.secondary_category_id')


def _get_group_pipeline(group_by):
    return [
        {
            '$group': {
                '_id': '$' + group_by,
                'count': {'$sum': 1},
            }
        },
        {
            '$project': {
                '_id': 0,
                'value': '$_id',
                'count': 1,
            }
        },
        {
            '$sort': {'count': -1}
        },
        {
            '$limit': 6,
        }
    ]


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