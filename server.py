import firebase_admin
from firebase_admin import firestore, credentials, messaging

from time import sleep

cred = credentials.Certificate("YOUR CREDENTIAL HERE")
firebase_admin.initialize_app(cred)
db = firestore.client()

def resolve_friend_requests(docs, changes, read_time):
    for change in changes:
        try:
            print("friend request change")
            if (change.type.name == "ADDED"):
                friend_request_info = change.document.to_dict()
                # TODO too many wheres here
                from_id = friend_request_info["from"]
                to_phone = friend_request_info["to"]
                from_phone = db.collection("users").document(from_id).get().to_dict()["phone"]
                print("friend request made %s %s" % (from_phone, to_phone))
                to_friend_query = db.collection("users")\
                                    .where("phone", "==", to_phone).get()
                for to_friend in to_friend_query:
                    to_id = to_friend.id
                    existing_request = db.collection("friend-requests")\
                                         .where("to", "==", from_phone)\
                                         .where("from", "==", to_id).get()
                    for request in existing_request:
                        batch = db.batch()
                        batch.delete(db.collection("friend-requests").document(change.document.id))
                        batch.delete(db.collection("friend-requests").document(request.id))
                        batch.update(db.collection("users").document(from_id), {"friends." + to_id: {}})
                        batch.update(db.collection("users").document(to_id), {"friends." + from_id: {}})
                        batch.commit()
        except Exception as e:
            print(e)

def get_notification(exp_type, from_id, to_id):
    from_name = db.collection("users").document(from_id).get().to_dict()["name"]
    to_name = db.collection("users").document(to_id).get().to_dict()["name"]
    title="unknown"
    body="unknown"
    if (exp_type == "THINKING"):
        title = from_name.split(" ")[0] + " is thinking of you!"
        body = "say something to them"
    elif (exp_type == "DOGPIC"):
        title = from_name.split(" ")[0] + " needs a cute picture!"
        body = "send them one"
    elif (exp_type == "STRESSED"):
        title = from_name.split(" ")[0] + " is stressed!"
        body = "say something to help them out"
    print("sending notification, %s | %s" % (title, body))
    return messaging.Notification(title=title, body=body)

def resolve_expression_requests(docs, changes, read_time):
    for change in changes:
        try:
            print("expression requests change")
            if (change.type.name == "ADDED"):
                request_info = change.document.to_dict()
                from_id = request_info["from"]
                to_ids = request_info["to"]
                print("expression added: %s %s" % (from_id, to_ids))
                
                batch = db.batch()
                batch.create(db.collection("expressions").document(change.document.id), change.document.to_dict())
                batch.delete(db.collection("expression-requests").document(change.document.id))
                batch.update(db.collection("users").document(from_id), {"expressions." + change.document.id: True})
                for to_id in to_ids:
                    try:
                        # validate that this user can send this request
                        has_friend = db.collection("users").document(to_id).get().to_dict()["friends"][from_id]
                    except KeyError:
                        print("trying to request someone who is not a friend")
                        continue
                    batch.update(db.collection("users").document(to_id), {"friends." + from_id +  "."+ change.document.id: True})

                    to_token = db.collection("users").document(to_id).get().to_dict()["fcmToken"]
                    messaging.send(messaging.Message(
                        notification=get_notification(request_info["type"], from_id, to_id),
                        data={"id": change.document.id},
                        token=to_token
                    ))
                batch.commit()
        except Exception as e:
            print(e)

def resolve_satisfied_expressions(docs, changes, read_time):
    for change in changes:
        try:
            print("expressions change")
            if (change.type.name == "MODIFIED") or (change.type.name == "ADDED"):
                request_info = change.document.to_dict()
                from_id = request_info["from"]
                to_ids = request_info["to"]
                satisfied = request_info["satisfied"]
                if not satisfied:
                   return
                print("expression satisfied: %s %s" % (from_id, to_ids))
                
                batch = db.batch()
                batch.delete(db.collection("expressions").document(change.document.id))
                batch.update(db.collection("users").document(from_id), {"expressions." + change.document.id: firestore.DELETE_FIELD})
                for to_id in to_ids:
                    batch.update(db.collection("users").document(to_id), {"friends." + from_id +  "."+ change.document.id: firestore.DELETE_FIELD})
                batch.commit()
        except Exception as e:
            print(e)

def watch_watch():
  friend_watch = db.collection("friend-requests").on_snapshot(resolve_friend_requests)
  expression_request_watch = db.collection("expression-requests").on_snapshot(resolve_expression_requests)
  expression_watch = db.collection("expressions").on_snapshot(resolve_satisfied_expressions)
  while True:
    if friend_watch._closed:
        friend_watch = db.collection("friend-requests").on_snapshot(resolve_friend_requests)
    if expression_watch._closed:
        expression_watch = db.collection("expressions").on_snapshot(resolve_satisfied_expressions)
    if expression_request_watch._closed:
        expression_request_watch = db.collection("expression-requests").on_snapshot(resolve_expression_requests)
    sleep(1)

watch_watch()
