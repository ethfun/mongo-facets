from pymongo import MongoClient

# connect to database test in localhost
client = MongoClient(host="localhost", port=27017)
db_auth = client.admin
db_auth.authenticate("admin", "secret")
db = client.opendata

# read from db
print(list(db.JX.find({}).limit(10)))