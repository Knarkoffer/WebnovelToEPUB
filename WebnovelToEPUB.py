#!python3
# coding: utf-8

"""
---------------------------------

Webnovel to EPUB

Version: 13

Script created to transform stories from webnovel.com into .epub-files,
to be read on my Kindle. Would usually use the otherwise excellent FanFicFare,
but it seems to only be able to grab unlocked chapters.

---------------------------------
"""

import time
import sys
import os
import ast
import argparse
import random

from bs4 import BeautifulSoup  # pip install beautifulsoup4 (http://www.crummy.com/software/BeautifulSoup/)
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import JavascriptException, TimeoutException, WebDriverException
from ebooklib import epub  # pip install EbookLib (https://github.com/aerkalov/ebooklib)


def exit_script():
    driver.quit()
    sys.exit()


def debug_print(output_string):
    if DEBUG_MODE:
        print(output_string)


def readystate_complete(d):
    # AFAICT Selenium offers no better way to wait for the document to be loaded,
    # if one is in ignorance of its contents.
    return d.execute_script("return document.readyState") == "complete"


def webdriver_get_soup(url):

    try:
        driver.get(url)
        time.sleep(1)

        WebDriverWait(driver, 30).until(readystate_complete)

        try:
            webpage_html = driver.execute_script("return document.getElementsByTagName('html')[0].innerHTML")
        except JavascriptException:
            webpage_html = driver.page_source

        if webpage_html:
            page_soup = BeautifulSoup(webpage_html, 'html.parser')
        else:
            page_soup = None

    except TimeoutException as e:
        page_soup = None
    except WebDriverException as e:
        page_soup = None

    return page_soup


def decompose_locked_chapters(chapters_soup):

    all_chapters = chapters_soup.findAll('a', href=True, class_="c_000 db pr clearfix pt8 pb8 pr8 pl8")

    debug_print(f"Total chapters: {len(all_chapters)}")

    for chapter in all_chapters:

        chapter_lock = chapter.find('svg', class_='fr _icon ml16 mt4 c_s fs16')

        chapter_number_container = chapter.find('i', class_='fl fs16 lh24 c_l _num mr4 tal')\

        if chapter_number_container:
            chapter_number = chapter_number_container.get_text()
        else:
            chapter_number = "N/A"

        chapter_title = chapter['title']

        if chapter_lock:
            debug_print(f"Decomposing {chapter_number} - {chapter_title}")
            chapter_lock.parent.parent.decompose()

    return chapters_soup


def get_book_metadata():

    book_metadata = dict()

    bookinfo_soup = webdriver_get_soup(f"{STORY_URL}")

    script_json = bookinfo_soup.find('script', type="application/ld+json").get_text().strip()
    bookinfo_json = ast.literal_eval(script_json)[0]

    book_metadata['Title'] = bookinfo_json['name']
    book_metadata['Author'] = bookinfo_json['author']['name']
    book_metadata['Language'] = "en"
    book_metadata['ID'] = bookinfo_json['mainEntityOfPage'].split('_')[-1].rstrip('/')

    return book_metadata


def create_epub_filename(metadata):

    # Transforms the title and author of the book to a suiting filename
    title_acsii = metadata['Title'].encode('ascii', 'ignore').decode().strip()
    author_ascii = metadata['Author'].encode('ascii', 'ignore').decode().strip()

    output_filename = f"{title_acsii} - {author_ascii}"
    output_filename = fix_windows_filename(output_filename) + ".epub"

    return output_filename


def fix_windows_filename(input_string):
    """
    Removes characters that are forbidden in filenames on Windows-systems
    fileName = fix_windows_filenames(fileName)
    """

    output_string = input_string

    output_string = output_string.replace('\\', '')
    output_string = output_string.replace('/', '')
    output_string = output_string.replace(':', '_')
    output_string = output_string.replace('*', '')
    output_string = output_string.replace('?', '')
    output_string = output_string.replace('"', '')
    output_string = output_string.replace('<', '')
    output_string = output_string.replace('>', '')
    output_string = output_string.replace('|', '')

    return output_string


parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument('-s', '--storyurl',
                    type=str, default="",
                    help='Story URL')

parser.add_argument('-c', '--cache',
                    action='store_true', default=False,
                    help="Saves the scraped chapters for future, thereby saving time and reduces site traffic")

parser.add_argument('-d', '--debug',
                    action='store_true', default=False,
                    help="Enables Debug-mode")

parser.add_argument('-g', '--geckopath',
                    type=str, default=r"C:\DATA\geckodriver.exe",
                    help="Path to geckodriver")


# -- Convert input arguments to variables
args = parser.parse_args()

# --storyurl :
STORY_URL = args.storyurl

# --savechapters :
SAVE_CHAPTERS = args.cache

# --debug :
DEBUG_MODE = args.debug

# --geckopath :
GECKODRIVER_PATH = args.geckopath

# Ensure that the user gives correct input
if not STORY_URL:
    parser.print_help()
elif not os.path.isfile(GECKODRIVER_PATH):
    sys.exit(f"No geckodriver found")

driver = webdriver.Firefox(executable_path=GECKODRIVER_PATH)
driver.set_window_size(700, 500)  # Changes the window-size, to be less intrusive
driver.get("https://passport.webnovel.com/login.html")

input(f"Please log in to the site, press [Return] when you've done so")

# This gets the book metadata
book_metadata = get_book_metadata()

# Creates the book item and configures it's metadata
book = epub.EpubBook()

# set metadata
book.set_identifier(book_metadata['ID'])
book.set_title(book_metadata['Title'])
book.set_language(book_metadata['Language'])
book.add_author(book_metadata['Author'])


# Transforms the title and author of the book to a suiting filename
epub_filename = create_epub_filename(book_metadata)

# Starts the spine list
book.spine = ['nav']

# Starts the chapter list
chapter_list = list()

CACHE_PATH = None

if SAVE_CHAPTERS:
    CACHE_PATH = os.path.join(os.getcwd(), book_metadata['ID'])
    if not os.path.isdir(CACHE_PATH):
        os.mkdir(CACHE_PATH)

allchapters_soup = webdriver_get_soup(f"{STORY_URL}/catalog")

# Removes all locked chapters
allchapters_soup = decompose_locked_chapters(allchapters_soup)

all_chapters = allchapters_soup.find_all('a', href=True, class_="c_000 db pr clearfix pt8 pb8 pr8 pl8")

print(f"Unlocked chapters: {len(all_chapters)}")
print(f"---------------------[ 0 / {len(all_chapters)} ]---------------------")

chapter_counter = 1
for chapter in all_chapters:

    chapter_cached = False

    chapter_url = chapter['href'].strip('//')
    chapter_number_container = chapter.find('i', class_='fl fs16 lh24 c_l _num mr4 tal')
    if chapter_number_container:
        chapter_number = chapter_number_container.get_text()
    else:
        chapter_number = "N/A"

    chapter_title = chapter['title']

    print(f"Chapter Counter: {chapter_counter}")
    print(f"Chapter Number: {chapter_number}")
    print(f"Chapter Title: {chapter_title}")

    if CACHE_PATH:
        if os.path.isfile(os.path.join(CACHE_PATH, f"chapter_{chapter_counter}.html")):
            chapter_cached = True
            print(f"Reading from cache")
            with open(os.path.join(CACHE_PATH, f"chapter_{chapter_counter}.html"), mode='r') as file:
                chapter_soup = BeautifulSoup(file.read(), 'html.parser')
        else:
            chapter_soup = webdriver_get_soup(f"https://{chapter_url}")
    else:
        chapter_soup = webdriver_get_soup(f"https://{chapter_url}")

    # Strips out the pirate message *afronted*
    piratethingy = chapter_soup.find_all('pirate')
    if piratethingy:
        for item in piratethingy:
            item.decompose()

    # Strips out the comment bubbles
    commentbubble = chapter_soup.find_all('i', class_="para-comment")
    if commentbubble:
        for item in commentbubble:
            item.decompose()

    chapter_paragraphs = chapter_soup.find_all('div', class_="cha-paragraph")

    chapter_html = f"<center><h2>{chapter_number}: {chapter_title}</h1></center>"
    for chapter_item in chapter_paragraphs:
        chapter_html = chapter_html + chapter_item.find('div', class_="dib pr").prettify()

    # Builds the epub chapter
    chapter = epub.EpubHtml(title=f"{chapter_number}: {chapter_title}", file_name=f"chap_{chapter_counter}.xhtml",
                            lang='en')
    chapter.content = chapter_html
    book.add_item(chapter)

    # Updates the ToC and Spine
    chapter_list.append(chapter)
    book.spine.append(chapter)

    if SAVE_CHAPTERS:
        with open(os.path.join(CACHE_PATH, f"chapter_{chapter_counter}.html"), mode='w') as file:
            file.write(chapter_soup.prettify())

    if not chapter_cached:
        if not int(chapter_counter) == len(all_chapters):
            if DEBUG_MODE:
                sleep_time = random.randint(1, 2)
            else:
                sleep_time = random.randint(15, 45)
            print(f"Waiting {sleep_time} seconds to reduce siteload...")
            print(f"---------------------[ {chapter_counter} / {len(all_chapters)} ]---------------------")
            time.sleep(sleep_time)
        else:
            print(f"---------------------[ {chapter_counter} / {len(all_chapters)} ]---------------------")
    else:
        print(f"---------------------[ {chapter_counter} / {len(all_chapters)} ]---------------------")

    chapter_counter += 1

# define Table Of Contents
book.toc = chapter_list

# TODO: Play with Section compartmenting
""" 
book.toc = (epub.Link('chap_1.xhtml', 'Chapter 1', 'chap_1'),
    (
        epub.Section('Languages'),
        (chapter, chapter2)
    )
)
"""

# add default NCX and Nav file
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

# define CSS style
style = 'BODY {color: white;}'
nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

# add CSS file
book.add_item(nav_css)

# write to the file
epub.write_epub(epub_filename, book, {})

print(f"Finished, EPUB created as {epub_filename}")

exit_script()
