import drawBot as db
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--output")
args = parser.parse_args()

db.newPage(200, 200)
db.fontSize(20)
db.text("hello world", (10, 100))
db.saveImage(args.output)
