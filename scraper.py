import argparse
import json
import re
import time
import urllib
import sys

import requests
from bs4 import BeautifulSoup as bs
from tqdm import tqdm

import helpers
from image import Image


class InstagramScraper:
    def __init__(self, args):
        self.username = args.username or input("insert username : ")
        self.username = self.username.strip()
        self.next = True
        self.first = True
        self.downloaded = 0
        self.images = []

    @property
    def soup(self):
        response = requests.get(self.url, timeout=10)
        if response.status_code == 404:
            print(f"Error : could not find user {self.username}.")
            sys.exit(1)
        html = response.text
        return bs(html, "lxml")

    def get_query_hash(self):
        print("checking user {}...".format(self.username))
        url = "http://instagram.com/static/bundles/metro/ProfilePageContainer.js/0e6032c4b4ec.js"
        script = requests.get(url, timeout=10).text
        self.query_hash = helpers.query_hash(script)

    @property
    def parsed_json(self):
        if self.first:
            pattern = "window._sharedData = "
            script = self.soup.find("script", text=re.compile(pattern))
            json_string = script.text.replace(pattern, "").replace(";", "")
            return json.loads(json_string)
        else:
            http_response = requests.get(self.url, timeout=10).text
            return json.loads(http_response)

    @property
    def url(self):
        if self.first:
            return f"https://www.instagram.com/{self.username}"
        else:
            variables = f'{{"id":"{self.id}","first":12,"after":"{self.end_cursor}"}}'
            # encode the variables with the UTF-8 encoding scheme
            encoded = urllib.parse.quote(variables)
            return f"https://www.instagram.com/graphql/query/?query_hash={self.query_hash}&variables={encoded}"

    def get_query_params(self):
        if self.first:
            print("getting user info...")
            data = self.parsed_json["entry_data"]["ProfilePage"][0]["graphql"]["user"]
            self.id = data["id"]
            if data["is_private"]:
                print("User account is private. Abort")
                quit()
        else:
            data = self.parsed_json["data"]["user"]
        edge_owner = data["edge_owner_to_timeline_media"]
        posts_count = edge_owner["count"]

        if posts_count == 0:
            print(f"user {self.username} has 0 posts")
            quit()

        page_info = edge_owner["page_info"]
        # get the needed data
        self.next = page_info["has_next_page"]
        self.end_cursor = page_info["end_cursor"]
        self.images = edge_owner["edges"]
        if self.first:
            helpers.print_same_line("starting download...")
            print()

    def download(self, image):
        image.download()
        self.downloaded += 1
        display = "downloaded {} images".format(self.downloaded)
        helpers.print_same_line(display)

    def download_children(self, image):
        for child in image.children:
            self.download(child)

    def download_images(self):
        for item in self.images:
            image = Image.from_json_data(item, self.username)
            if image.is_video:
                continue
            self.download(image)
            if image.has_children:
                image.get_children()
                self.download_children(image)

    def loop(self):
        while self.next:
            self.get_query_params()
            self.download_images()
            self.first = False

    def scrape(self):
        helpers.make_folder(self.username)
        self.loop()
        if self.downloaded > 0:
            print(f"\nsuccessully downloaded {self.downloaded} images")
        else:
            print("no images were found.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username", help="specify the username", metavar="")
    args = parser.parse_args()
    scraper = InstagramScraper(args)
    scraper.get_query_hash()
    scraper.scrape()


if __name__ == "__main__":
    main()
