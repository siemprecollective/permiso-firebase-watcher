import firebase_admin
from firebase_admin import firestore, credentials, messaging

from time import sleep

cred = credentials.Certificate("YOUR CREDENTIAL HERE")
firebase_admin.initialize_app(cred)
db = firestore.client()

docs = db.collection("expressions").get()

for doc in docs:
    doc.reference.update({"satisfied": True})
