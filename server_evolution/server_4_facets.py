from flask import Flask, request, jsonify
from pymongo import MongoClient
import re

app = Flask(__name__, static_folder='../client')
# PRO
client = MongoClient(host="localhost", port=27017)
db_auth = client.admin
db_auth.authenticate("admin", "secret")

db = client.opendata
API_ENDPOINT = '/api/v1'

def _get_array_param(param):
    return list(filter(None, param.split(",")))

def _get_re_array_param(params):
    return [re.compile('.*' + param + '.*') for param in filter(None, params.split(","))]

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
    sources = _get_re_array_param(request.args.get('sources', ''))

    find = {}
    if search:
        find['$text'] = {'$search': search}
    if sources:
        # boroughs
        find['data.original_primary_key'] = {'$in': sources}
    if brands:
        # boroughs
        find['data.brand_alpha'] = {'$in': brands}
    if primary_category_ids:
        # cuisines
        find['data.primary_category_id'] = {'$in': primary_category_ids}
    if secondary_category_ids:
        # address.zipcode
        find['data.secondary_category_id'] = {'$in': secondary_category_ids}

    print(find)
    response = {
        'restaurants': list(db.product.find(find).skip(skip).limit(limit)),
        'count': db.product.find(find).count(),
        'defaultsBrandAlpha': omit_field_count('data.brand_alpha'),
        'defaultsOriginalPrimaryKey': omit_field_count('data.original_primary_key'),
        'defaultsPrimaryCategoryId': omit_field_count('data.primary_category_id')
    }

    for restaurant in response['restaurants']: # remove _id, is an ObjectId and is not serializable
        del restaurant['_id']
    return jsonify(response)

def omit_field_count (field):
    body = {field: {'$exists': False}}
    return db.product.count(body)

@app.route(API_ENDPOINT + "/restaurants/facets")
def restaurant_facets():
    # filters
    search = request.args.get('search', '')
    brands = _get_array_param(request.args.get('boroughs', ''))
    primary_category_ids = _get_array_param(request.args.get('cuisines', ''))
    secondary_category_ids = _get_array_param(request.args.get('zipcodes', ''))
    sources = _get_re_array_param(request.args.get('sources', ''))

    pipeline = [{
        '$match': {'$text': {'$search': search}}
    }] if search else []

    pipeline += [{
        '$facet': {
            'sources': _get_facet_source_pipeline(brands, primary_category_ids, secondary_category_ids),
            'brands': _get_facet_brand_pipeline(sources, primary_category_ids, secondary_category_ids),
            'primaryCategoryIds': _get_facet_primary_category_pipeline(sources, brands, secondary_category_ids),
            'secondaryCategoryId': _get_facet_secondary_category_pipeline(sources, brands, primary_category_ids),
        }
    }]

    print(pipeline)
    restaurant_facets = list(db.product.aggregate(pipeline))[0]

    return jsonify(restaurant_facets)

def _get_facet_source_pipeline(brands, primary_category_ids, secondary_category_ids):
    match = {}

    if brands:
        match['data.brand_alpha'] = {'$in': brands}
    if primary_category_ids:
        match['data.primary_category_id'] = {'$in': primary_category_ids}
    if secondary_category_ids:
        match['data.secondary_category_id'] = {'$in': secondary_category_ids}

    pipeline = [
        {'$match': match}
    ] if match else []

    return pipeline + _get_group_pipeline('data.original_primary_key')

def _get_facet_brand_pipeline(sources, primary_category_ids, secondary_category_ids):
    match = {}

    if sources:
        match['data.original_primary_key'] = {'$in': sources}
    if primary_category_ids:
        match['data.primary_category_id'] = {'$in': primary_category_ids}
    if secondary_category_ids:
        match['data.secondary_category_id'] = {'$in': secondary_category_ids}

    pipeline = [
        {'$match': match}
    ] if match else []

    return pipeline + _get_group_pipeline('data.brand_alpha')

def _get_facet_primary_category_pipeline(sources, brands, secondary_category_ids):
    match = {}

    if sources:
        match['data.original_primary_key'] = {'$in': sources}
    if brands:
        match['data.brand_alpha'] = {'$in': brands}
    if secondary_category_ids:
        match['data.secondary_category_id'] = {'$in': secondary_category_ids}

    pipeline = [
        {'$match': match}
    ] if match else []

    # return pipeline + _get_group_pipeline('cuisine')
    return pipeline + _get_group_pipeline('data.primary_category_id')


def _get_facet_secondary_category_pipeline(sources, brands, primary_category_ids):
    match = {}

    if sources:
        match['data.original_primary_key'] = {'$in': sources}
    if brands:
        match['data.brand_alpha'] = {'$in': brands}
    if primary_category_ids:
        match['data.primary_category_id'] = {'$in': primary_category_ids}

    pipeline = [
        {'$match': match},
    ] if match else []

    return pipeline + _get_group_pipeline('data.secondary_category_id')

def _get_group_pipeline(group_by):
    if group_by == 'data.original_primary_key':
        return [
            {"$project": {
                'original_primary_key': {"$split": ['$' +group_by, ":"]}
            }},
            {"$project": {
                # Specifies the inclusion of a field. <1 or true>
                "original_primary_key": 1,
                # 然后使用$arrayElemAt获得$original_primary_key的地区数组中第一个元素，命名为 source
                "source": {
                    "$arrayElemAt": ["$original_primary_key", 0]
                }}
            },
            {
                '$group': {
                    '_id': '$source',
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
    elif group_by == 'data.primary_category_id' or group_by == 'data.secondary_category_id':
        return [
            {
                '$group': {
                    '_id': {'id': '$' + group_by,
                            'name': '$' + group_by.replace('_id', ''),
                            },
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
    else:
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

@app.route('/go/chart')
def chart():
  return app.send_static_file('stats.html')

@app.route('/<path:path>')
def static_proxy(path):
  # send_static_file will guess the correct MIME type
  return app.send_static_file(path)

# run the application without flask-cli
if __name__ == "__main__":
    app.run(debug=True)