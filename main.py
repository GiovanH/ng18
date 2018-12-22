#!/bin/python3

from bs4 import BeautifulSoup
import argparse
import loom
import traceback
import json
import jfileutil as jobj
from urllib.request import urlopen
from urllib.request import urlretrieve
from os import path, makedirs
import re

class GalleryItem():

    def __init__(self, fullimage, author, imagename, thumbnail=None, suitability="unknown"):
        super(GalleryItem, self).__init__()
        self.image = fullimage
        self.author = author
        self.name = imagename
        self.thumbnail = thumbnail
        self.suitability = suitability

        self.ext = "." + re.split("\.|\?", fullimage)[-2]
        if len(self.ext) != 4:
            print("[WARN] Weird file extension on link {}".format(fullimage))

    def dump(self):
        for a in ["image", "author", "name", "thumbnail", "suitability", "ext"]:
            print("{}: {}".format(a, self.__getattribute__(a)))       


def getUserPage(username, page):
    user_page_url = "https://{}.newgrounds.com/{}/".format(username, page)
    user_page_bs4 = BeautifulSoup(urlopen(user_page_url), features="html.parser") 
    return user_page_bs4


def getDataJSON(bs4page, test=True):
    user_scripts = bs4page.findAll("script")
    showcase_template = bs4page.find("script", id="showcase-template")
    user_js = user_scripts[user_scripts.index(showcase_template) + 1]
    jstxt = user_js.text
    starttok = "var years = {"
    startpos = jstxt.find(starttok) + len(starttok)
    endpos = jstxt.find(",\n    \"sequence\"")
    userjson = "{" + jstxt[startpos:endpos] + "}"

    if test:
        with open("test.json", "w") as jsonfile:
            jsonfile.write(userjson)

    return userjson
 

def htmlToItem(htmltxt):
    global spam
    global fullpage_bs4

    # Grab the preview html
    spam = BeautifulSoup(htmltxt, features="html.parser")

    # Scrape the preview html 
    thumbnail = spam.img.get("src")
    fullpage_href = spam.a.attrs.get("href")

    suitability = spam.find("div", attrs={"class": "item-suitability"}).attrs.get("class")
    suitability.remove("item-suitability")
    suitability = suitability[0]

    # Fetch the full page
    fullpage_bs4 = BeautifulSoup(urlopen("https:" + fullpage_href), features="html.parser") 

    try:
        fullimage = fullpage_bs4.find(id="portal_item_view").img.attrs.get("src")
    except AttributeError:
        # Fallback for some pixel art
        fullimage = fullpage_bs4.find(attrs={"class": ["pod-body", "image"]}).img.attrs.get("src")

    imagename = fullpage_bs4.find("h2", attrs={"itemprop": "name"}).text
    author = fullpage_bs4.find("div", attrs={"class": "item-user"}).h4.a.text

    # Bring it all together
    return GalleryItem(
        fullimage,
        author,
        imagename=imagename,
        thumbnail=thumbnail,
        suitability=suitability)


def downloadAllImages(username):
    # user_mainpage_url = "https://{}.newgrounds.com/".format(username)
    # user_mainpage_bs4 = BeautifulSoup(urlopen(user_mainpage_url), features="html.parser")
    user_artpage = getUserPage(username, "art")
    user_json_s = getDataJSON(user_artpage)
    user_json = json.loads(user_json_s)
    for year in user_json.get("years"):
        for item in user_json.get("years").get(year).get("items"):
            try:
                loom.threadWait(8, 2)
                galleryItem = htmlToItem(item)
                galleryItem.dump()
                basepath = path.join(".", galleryItem.author)
                makedirs(basepath, exist_ok=True)
                filepath = path.join(basepath, galleryItem.name + galleryItem.ext)
                loom.thread(target=lambda: urlretrieve(galleryItem.image, filename=filepath))
            except AttributeError as e:
                traceback.print_exc()
                jobj.save(item, "item_error_{}".format(hash(item)))
                raise


def parse_args():
    """
    Parse args from command line and return the namespace
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("user",
                    help="File globs that select which files to check. Globstar supported.")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    downloadAllImages(args.user)
