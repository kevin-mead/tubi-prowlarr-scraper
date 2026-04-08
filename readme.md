# Tubi/Prowlarr Scraper

Tubi carries such a niche selection of licensed content that it made me curious whether it was all readily available via public torrent trackers. This Python answers that question one page at a time! (Maybe one day it will be able to do this headless via CRON job, who knows...)

## Setup

First, download the "Python" folder in this repo.

Set up a Python 3 environment (eg VScode). The python part of this project only really has [BeautifulSoup](https://pypi.org/project/beautifulsoup4/) as a dependency that you need to download (bs4 to be exact).

[Download Prowlarr](https://prowlarr.com/#download). Prowlarr lets you choose a bunch of torrent sources, like TPB, 1337x.to, YTS, etc, and then host a local API to fetch their metadata. This Python just assumes that you are broadcasting the API on localhost:9696 (the default). You'll need your local API key when you run the python script. To get this, go to http://localhost:9696, then settings->general->API key. Also, make sure you add some torrent sites for it to scrape.

## Getting The Tubi Data

We're gonna get the data the dumb way.

Go to any page on tubitv.com, scroll all the way to the bottom, open inspect element, then go to the body tag, right click and choose "copy outer HTML". Then, paste it into a code editor and save it as an HTML file.

*Why do this and not press CTRL/CMD+S or CMD+U?* Because Tubi is a modern website with modern framework, and doesn't load all their divs when you do that.

There are smarter ways to get this data, for sure...but this works! And generally never rate limits.

## Loading Everything Up

Keep the python file in its folder, load it into an environment (like VScode) and run it.

It's gonna ask you for a few things:
- Your API key (it will store this for you later so you don't have to re-enter, unless it fails)
- The file path to your HTML file(s) (you can load as many as you want and name each HTML capture on the output sheet)

Once you let it rip, it will fetch a new result from Prowlarr every 0.5 seconds to be nice to the API. You can reduce this time in the code by changing "REQUEST_DELAY = 0.5" to something else.

The CSV will go into the source folder for the Python and will be named with a timestamp.

## Done!

You now have a bunch of data from Tubi and Prowlarr put together! See "example-output.csv" for an example of the resulting data.

## AI Use

This is a one weekend project with very few possible security implications. The Python was written by Kimi 2.5. I ideated and then generated it so you don't have to!
