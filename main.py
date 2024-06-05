"""
## Importing all the required libraries
import twitter
import networkx
import sys
import time
from functools import partial
from sys import maxsize as maxint
from urllib.error import URLError
from http.client import BadStatusLine
import matplotlib.pyplot as plt
import pickle
import datetime

counter = 0                                                       #Initializing counter
filehandler = open(b"Output1.txt","wb")                           #Initializing filehandler

"""Setting up the Twitter API using OAuth authentication."""
def oauth_login():
    CONSUMER_KEY = '4tMTcSOIMdI7zVksOKp6JO2Uz'
    CONSUMER_SECRET = '6ZCBQNBwGZYsfB8yhBTzHn7sS1iy269GyhfGVX26NLJXQR6l1h'
    OAUTH_TOKEN = '509692311-xrLqxEpGOF8jGE0IfaFYSv0tKDNuuiP4n6OxCpOZ'
    OAUTH_TOKEN_SECRET = 'FQd7N4KAxukbSm3CpuUahpU44tAjMUbqQpFZKCy5PYj2V'
    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET)
    twitter_api = twitter.Twitter(auth=auth)
    return twitter_api

""" make_twitter_request() is a helper function to handle HTTP errors that occurs while making requests to Twitter API. 
    It retries request with increased wait period if errors are encountered. 
    This function was refereed and modified from "Mining the Social Web, 3rd Edition - Chapter 9: Twitter Cookbook"."""
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):

    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):
        if wait_period > 3600:  # Seconds
            printFunc('Too many retries. Quitting.', file=sys.stderr)
            raise e
        if e.e.code == 401:
            printFunc('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            printFunc('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429:
            printFunc('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                printFunc("Retrying in 5 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60 * 5 + 5)
                printFunc('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e  # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            printFunc('Encountered {0} Error. Retrying in {1} seconds'.format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    wait_period = 2
    error_count = 0
    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            printFunc("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                printFunc("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            printFunc("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                printFunc("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise

""" This function gets the followers and friend IDs of any Twitter user, it uses make_twitter_request() function to 
handle errors. This function was refereed and modified from "Mining the Social Web, 3rd Edition - Chapter 9: Twitter 
Cookbook". """
def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):
    assert (screen_name != None) != (user_id != None), \
        "Must have screen_name or user_id, but not both"
    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)
    friends_ids, followers_ids = [], []

    for twitter_api_func, limit, ids, label in [
        [get_friends_ids, friends_limit, friends_ids, "friends"],
        [get_followers_ids, followers_limit, followers_ids, "followers"]
    ]:
        if limit == 0: continue
        limit = 5000
        cursor = -1
        while cursor != 0:
            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else:  # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            printFunc('Fetched {0} total {1} ids for {2}'.format(len(ids), \
                                                             label, (user_id or screen_name)), file=sys.stderr)

            if len(ids) >= limit or response is None:
                break
    return friends_ids[:friends_limit], followers_ids[:followers_limit]

""" This function is used to analyze a user's frineds and followers. It was refereed and modified from the book "Mining
the Social Web, 3rd Edition - Chapter 9: Twitter Cookbook". """
def setwise_friends_followers_analysis(screen_name, friends_ids, followers_ids):
    friends_ids, followers_ids = set(friends_ids), set(followers_ids)                 # Converts friends_ids, followers_ids to set to use set operations.
    printFunc('{0} is following {1}'.format(screen_name, len(friends_ids)))           # Gives the number of people the user is following.
    printFunc('{0} is being followed by {1}'.format(screen_name, len(followers_ids))) # Gives the number of people that are following the user.
    printFunc('{0} of {1} are not following {2} back'.format(                         # Gives the number of people that not following back the user.
        len(friends_ids.difference(followers_ids)),
        len(friends_ids), screen_name))
    printFunc('{0} of {1} are not being followed back by {2}'.format(                 # Gives the number of people that the user is not following back.
        len(followers_ids.difference(friends_ids)),
        len(followers_ids), screen_name))
    printFunc('{0} has {1} mutual friends'.format(                                   # Gives the number  mutual friends.
        screen_name, len(friends_ids.intersection(followers_ids))))

"""This function get the user's ID and name, it uses the make_twitter_request() to handle errors."""
def get_nameID(screenName):
    try:
        screenName = int(screenName)
        user = make_twitter_request(twitter_api.users.lookup, user_id=screenName)
    except:
        name = screenName.replace(" ","")
        user = make_twitter_request(twitter_api.users.lookup,screen_name=name)
    user = user[0]
    name_id = (user["id"], user["name"])
    return name_id

"""This function add the 5 popular friends of a user tot the networkx graph and connects them to the user node."""
def add_popular_5(parent, children, graph):
    for i in children:
        graph.add_node((i[0],i[1]))
        graph.add_edge((parent[0], parent[1]), (i[0],i[1]))

"""This function accepts list of int (number of followers of each user) and finds index of top 5 maximum values 
(top most popular friends) in the list."""
def max_5_index(list):
    indexes = []
    def maxIndexFinder(numOfFollowers, acc, num):      #Nested function to extract top 5 index to store in indexes list.
        if num > 0 and len(numOfFollowers)!=0:
            try:
                maximum = numOfFollowers[0]
                max_index = 0
                for i in range(len(numOfFollowers)):
                    if (numOfFollowers[i] > maximum):
                        maximum = numOfFollowers[i]
                        max_index = i
                acc.append(max_index)
                numOfFollowers[max_index] = 0
                maxIndexFinder(numOfFollowers, acc, num - 1)
            except:
                print("ERROR: No Followers found for", acc)                      # In case users have no followers.
    maxIndexFinder(list, indexes, 5) # Function taking input list, index list and 5 to find the top 5 index in the list.
    printFunc(indexes)
    return indexes

"""This function finds such users in the network that follows each other i.e reciprocal friends for the parent node
 and for a given depth. It recursively finds the top 5 friends of each node to a certain depth and adds them to the graph."""
def get_reciprocal_friends(twitter_api, parent, depth, graph):
    if depth > 0:
        printFunc("Current number of nodes in the graph:", graph.number_of_nodes())
        printFunc("Starting Point:")
        printFunc(parent)
        top5 = find_5_popular_friends(twitter_api, parent[0])       # Gets the top 5 friends of parent from the user ID.
        printFunc("The 5 Most popular friends are: ")
        printFunc(top5)
        add_popular_5(parent, top5, graph)                          # Adding the popular friends to the graph, connected to the parent.
        for i in top5:
            get_reciprocal_friends(twitter_api, i,depth-1,graph)    # Looping on the top5 list to get reciprocal friends for each of them.

""" This function get's the followers, following, reciprocal friends and finally the 5 most popular friends of the specified node."""
def find_5_popular_friends(twitter_api, user_id):
    popular_friends = []
    list_of_tuples = []
    followers_nums = []
    try:
        # Retrieving the list of users that the user is following and list of followers of the given user.
        following, followers = get_friends_followers_ids(twitter_api, user_id=user_id, friends_limit=maxint, followers_limit=maxint)
        # Converting both the lists to set so the set interaction method can be used to get the common elements.
        following = set(following)
        followers = set(followers)
        printFunc("Following:", followers)
        printFunc("Followers:", following)
        # Converting the resulting set to a lsist and storing the first 100 elements in 'reciprocal' seperated by commas.
        reciprocal = followers.intersection(following)
        reciprocal = list(reciprocal)
        reciprocal = ','.join([str(item) for item in reciprocal[:100]])

        all_reciprocals = make_twitter_request(twitter_api.users.lookup,user_id=reciprocal)
        printFunc("Reciprocals:", all_reciprocals)
# Iterating over all_reciprocals and extracting user details and combining them into a tuple namely 'all_together'.
        for i in all_reciprocals:
            num_followers = i["followers_count"]
            protected_users = i["protected"]
            id = i["id"]
            name = i["screen_name"]
            all_together = (id, name, num_followers, protected_users)
            list_of_tuples.append((all_together))
        list_of_actual_users = [x for x in list_of_tuples if x[3] == False]              #Filtering out private accounts.
        print(list_of_actual_users)
        for i in list_of_actual_users:
            followers_nums.append(i[2])     #Appending the user followers in the list who does not have a private account.
        five_index = max_5_index(followers_nums) # Calling max_5_index to find indices of top 5 max values in these followers.
# Iterating over indexes in five_index and retrieving id and name of 5 most popular friends.
        try:
            for j in five_index:
                popular_friends.append((list_of_actual_users[j][0], list_of_actual_users[j][1]))
        except:
            printFunc("Unexpected error:", sys.exc_info())
        printFunc("These are the top 5 popular friends:")
        printFunc(popular_friends)
        return popular_friends
    except:
       printFunc("Unexpected Error :", sys.exc_info()[0])
       return popular_friends

"""This function creates a reciprocal friends tree for user."""
def make_reciprocal_tree(twitter_api,user_ID,depth):
    tree = networkx.Graph()
    seed = get_nameID(user_ID)
    tree.add_node((seed[0],seed[1]))
    get_reciprocal_friends(twitter_api,seed,depth,tree) # Populating graph with nodes and edges.
    return tree

"""This function is used to write to the console as well as to the output file"""
def printFunc(*args, **kwargs):
    pickle.dump("\n", filehandler)
    pickle.dump(" ".join(map(str, args)), filehandler)
    print(" ".join(map(str, args)))

if __name__ == '__main__':
    twitter_api = oauth_login()
    f = open("Output2.txt", "w+")                                        # Opening a file in write mode.
    firstDT = datetime.datetime.now()
    screenName = "edmundyu1001"
    tree = make_reciprocal_tree(twitter_api,get_nameID(screenName)[0],3) # Creating a tree of depth 3 i.e 125 nodes.
    networkx.draw(tree, with_labels=1)                                   # Draw the tree graph with labels for each node.

    #Prints various details about the tree graph to the console and the output files.
    printFunc("Total number of Nodes:", tree.number_of_nodes())
    string = "Total number of Nodes: " + str(tree.number_of_nodes())
    f.write(string)
    printFunc("Total number of Edges:", tree.number_of_edges())
    string = "\nTotal number of Edges: "+ str(tree.number_of_edges())
    f.write(string)
    printFunc("Diameter of the tree:", networkx.diameter(tree))
    string = "\nDiameter of the tree: "+ str(networkx.diameter(tree))
    f.write(string)
    string = "\nAverage Distance:"+ str(networkx.average_shortest_path_length(tree))
    f.write(string)
    printFunc("Average Distance:", networkx.average_shortest_path_length(tree))

    #Printing the total time taken to execute the program to the console and output file.
    lastDT = datetime.datetime.now()
    printFunc("\n_________________RUNTIME:", str(lastDT-firstDT), "__________________\n")
    string = "\nRUNTIME:" + str(lastDT-firstDT)
    f.write(string)

    plt.savefig("Map.png")                      # Save an image of the tree graph to Map.png
    plt.show()                                  # Displaying the tree graph
    filehandler.close()                         # Closing the file writers
    f.close()
