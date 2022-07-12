from ast import Return
from cgitb import text
from hashlib import new
from xml.dom.minidom import TypeInfo
from flask import jsonify, request, g, abort
from sqlalchemy import false

from api import api
from db.shared import db
from db.models.user_post import UserPost
from db.models.user import User
from db.models.post import Post

from db.utils import row_to_dict
from middlewares import auth_required
import jwt
import os


def authorid_validator(authorIds):

    if authorIds == None:
        return jsonify({"error": "authorIds is a required field"}), 400

    if isinstance(authorIds, str) == false:
        return (
            jsonify({"error": "unsupported format of authorIds, String expected"}),
            412,
        )
    return True


def collecting_data(authorIds):
    """
    Returns the post associated with given authorIds
    Return: List
    """
    seen_ids = {}
    posts = []

    for id in authorIds.split(","):

        if id.isnumeric() == True:
            # try to get post by id if vaild
            try:
                for post in Post.get_posts_by_user_id(id):
                    if post.id not in seen_ids:
                        # format json based on data
                        posts.append(
                            {
                                "tags": post.tags,
                                "id": post.id,
                                "text": post.text,
                                "likes": post.likes,
                                "reads": post.reads,
                                "popularity": post.popularity,
                            }
                        )
                    seen_ids[post.id] = "found"
            except:
                # if not valid goes to next id
                continue

    return posts


def sort_data(data, sortingParam, direct):

    # sorting array based on direction param given by the user
    if len(data) == 0:
        return data

    if direct == "desc":

        data.sort(key=lambda item: item[sortingParam], reverse=True)
    else:

        data.sort(key=lambda item: item[sortingParam])

    return data


def author_Validation(userId, post):
    result = False
    user = None
    for author in post.users:

        if author.id == userId:
            result = True
            user = author
    return result, user


def updateDatabase(authorIds, tags, text, post):
    # User.query.filter(User.id == username).one()

    # adding the new authorID's to the post
    if authorIds != None:
        newposts = []
        for id in authorIds:

            if type(id) == int:

                try:
                    user = User.query.filter(User.id == int(id)).one()

                    user.posts = user.posts.append(post)
                    newposts.append(user)

                except:
                    user = User(id=int(id), posts=[post])
                    newposts.append(user)
        queryPost = Post.query.filter(Post.id == post.id).one()
        queryPost.users = newposts
        db.session.flush()

    # adding new tags to post
    queryPost = Post.query.filter(Post.id == post.id).one()

    # updating the tags with given parameters
    if tags != None:

        queryPost.tags = tags
    # updating the text with given parameters
    if text != None:

        queryPost.text = text


@api.post("/posts")
@auth_required
def posts():
    # validation
    user = g.get("user")
    if user is None:
        return abort(401)

    data = request.get_json(force=True)
    text = data.get("text", None)
    tags = data.get("tags", None)
    if text is None:
        return jsonify({"error": "Must provide text for the new post"}), 400

    # Create new post
    post_values = {"text": text}
    if tags:
        post_values["tags"] = tags

    post = Post(**post_values)
    db.session.add(post)
    db.session.commit()

    user_post = UserPost(user_id=user.id, post_id=post.id)
    db.session.add(user_post)
    db.session.commit()

    return row_to_dict(post), 200


@api.get("/posts")
@auth_required
def gets():
    """
    Fetching posts with matching author Id's
    json body is expected to contain {authorIds: String (required), sortBy:String (optional) ,direction:String (optional)}
    """

    # validation
    user = g.get("user")
    if user is None:
        return abort(401)

    # gathering query parameters
    authorIds = request.args.get("authorIds", None)
    sortBy = request.args.get("sortBy", "id").lower()
    direction = request.args.get("direction", "asc").lower()

    # validating given parameters
    if authorIds == None:
        return jsonify({"error": "authorIds is a required field"}), 400

    if isinstance(authorIds, str) == false:
        return (
            jsonify({"error": "unsupported format of authorIds, String expected"}),
            412,
        )

    if isinstance(sortBy, str) == false:
        return jsonify({"error": "unsupported format of sortBy, String expected"}), 412

    if sortBy not in ["id", "reads", "likes", "popularity"]:
        return (
            jsonify(
                {
                    "error": "unsupported value for sortBy ,  expected: id, reads, likes, popularity"
                }
            ),
            400,
        )

    if isinstance(direction, str) == false:
        return (
            jsonify({"error": "unsupported format of direction, String expected"}),
            412,
        )

    if direction not in ["asc", "desc"]:
        return (
            jsonify({"error": "unsupported value for sortBy,  expected: asc, desc"}),
            400,
        )

    # fetching post associated with authorIds
    unsorted_post = collecting_data(authorIds)

    # sorted post based on query params
    sorted_posts = sort_data(unsorted_post, sortBy, direction)

    return jsonify({"posts": sorted_posts}), 200


@api.patch("/posts/<postid>")
@auth_required
def patch(postid):
    user = g.get("user")
    if user is None:
        return abort(401)

    # gartering data from request
    data = request.get_json()

    try:
        authorIds = data["authorIds"]
    except:
        authorIds = None

    try:
        tags = data["tags"]
    except:
        tags = None

    try:
        text = data["text"]
    except:
        text = None

    # decode the x-access-token to verify if the user is the author of the post
    secret = os.environ.get("SESSION_SECRET")
    userid = jwt.decode(
        request.headers.get("x-access-token"), secret, algorithms=["HS256"]
    )["id"]

    if postid.isnumeric() == False:
        return (
            jsonify({"error": "unsupported format of postId, integer expected"}),
            412,
        )

    # looping throw all the post by the user
    for post in Post.get_posts_by_user_id(userid):
        if post.id == int(postid):
            # if not author error
            result, author = author_Validation(userid, post)
            if result == False:
                return (
                    jsonify({"error": "Only the author of a post can update a post"}),
                    401,
                )

            # updating data on the database
            updateDatabase(authorIds, tags, text, post)
            updatedPost = Post.query.filter(Post.id == post.id).one()
            newAuthors = []

            for x in updatedPost.users:

                newAuthors.append(x.id)
            # formatting request for user
            result = {
                "authorIds": newAuthors,
                "id": updatedPost.id,
                "likes": updatedPost.likes,
                "popularity": updatedPost.popularity,
                "reads": updatedPost.reads,
                "text": updatedPost.text,
                "tags": updatedPost.tags,
            }

            return jsonify({"post": result}), 200
    return jsonify({"error": "You have not created any post by that ID"}), 400
