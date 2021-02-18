from pyspark import SparkConf, SparkContext
from pyspark.streaming import StreamingContext
from pyspark.sql import SQLContext
from pyspark.sql.types import *
from pyspark.sql.session import SparkSession
from pyspark.streaming.kafka import KafkaUtils
import pandas as pd
import sys
from textblob import TextBlob
from constants import *

# Defines if a tweet is positive, neutral or negative
# https://stackoverflow.com/a/48874376/3780957
def check_positive_negative(tweet):
    tweet = tweet.split(' ')
    positive = len([w for w in tweet if w in words_positive])
    negative = len([w for w in tweet if w in words_negative])
    # Check what is trending
    if (positive > negative):
        res = 'Positive'
    elif (positive < negative):
        res = 'Negative'
    else:
        res = 'Dubious'
    return res

# create spark configuration
conf = SparkConf()
conf.setAppName("Bitcoin_Recommender")

# create spark context with the above configuration
sc = SparkContext(conf=conf)
sc.setLogLevel("ERROR")

# create the Streaming Context from the above spark context with interval size 2 seconds
# Only one StreamingContext can be active in a JVM at the same time. (https://spark.apache.org/docs/2.0.0/streaming-programming-guide.html)
ssc = StreamingContext(sc, 2)

# setting a checkpoint to allow RDD recovery
# TODO: setting a checkpoint to allow RDD recovery
ssc.checkpoint("checkpoint_TwitterApp")

# Read word for sentiment analysis
spark = SparkSession(sc)
# Converted to Python lists
# https://stackoverflow.com/a/64764406/3780957
words_positive = spark.read.option("header", "false").csv("words/positive-words.txt").select('_c0').rdd.flatMap(list).collect()
words_negative = spark.read.option("header", "false").csv("words/negative-words.txt").select('_c0').rdd.flatMap(list).collect()

# read data from the port
dataStream = KafkaUtils.createStream(ssc, KAFKA_ZOOKEEPER_SERVERS, 'streaming-consumer', {KAFKA_TOPIC: 1})
# No need to decode() from 'utf-8' in Python3
dataStream = dataStream.map(lambda x: x[1].lower())
# Split each single tweet. The "end of tweet" was set at the Twitter pull application
lines = dataStream.flatMap(lambda line: line.split('_eot'))
# Filter the null or hashtags
lines = lines.filter(lambda x: x not in ['', ' ', '#'])
# Remove '_eot' and add counter
tweets = lines.map(lambda x: check_positive_negative(x))
tweets = tweets.map(lambda x: (x, 1))

# Reduce using a window
tweets_totals = tweets.reduceByKeyAndWindow(lambda x, y: x + y, lambda x, y: x - y, 10, 2)
# Sort descending by key
sorted_ = tweets_totals.transform(lambda rdd: rdd.sortBy(lambda x: x[1], ascending=False))
sorted_.pprint()

# start the streaming computation
ssc.start()

# wait for the streaming to finish
ssc.awaitTermination()

