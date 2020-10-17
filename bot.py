"""

Usage:
    slackbot [options]

Options:
    --config-file=<file>        Config file path.
"""
import io
import os
import sys
import time
import random

import yaml
from docopt import docopt
from slackclient import SlackClient

import requests
from urllib.parse import unquote

class SlackBot(object):

    def __init__(self, config=None):
        self.config = config
        self.token = self.config.get('slack_token')
        self.slack_client = SlackClient(self.token)
        self.bot_id = self.get_bot_id()

        self.respond_to = ['list',
                           'graph <name>',
                           'custom <url>']
        self.help_msg = '```\n'
        for answer in self.respond_to:
            self.help_msg += f'{answer}\n'
        self.help_msg += '```'

        # This is a set of predefined shortcuts for commonly used graphs
        self.graph_urls = {}
        self.puppetron = self.config.get('puppetron')
        self.graph_shortcuts = '```\n'
        for name, url in config['graph_urls'].items():
            self.graph_urls[name] = url
            self.graph_shortcuts += f'{name} - {url}\n'
        self.graph_shortcuts += '```'

    def get_bot_id(self):
        api_call = self.slack_client.api_call("users.list")
        if api_call.get('ok'):
            # List all users so we can find our bot
            users = api_call.get('members')
            for user in users:
                if 'name' in user and user.get('name') == self.config.get('bot_name'):
                    return "<@" + user.get('id') + ">"

            return None

    def start(self):
        if self.slack_client.rtm_connect():
            print("Bot is alive and listening for messages...")
            while True:
                events = self.slack_client.rtm_read()
                for event in events:
                    if event.get('type') == 'message':
                        # If we received a message, read it and respond if necessary
                        self.on_message(event)

                time.sleep(1)
        else:
            print('Connection failed, invalid token?')
            sys.exit(1)

    def on_message(self, event):
        # Ignore edits and uploads
        subtype = event.get('subtype', '')
        if subtype == u'message_changed' or subtype == u'file_share':
            return

        # Don't respond to messages sent by the bot itself
        if event.get('user', '') == self.bot_id:
            return

        full_text = event.get('text', '') or ''

        # Only respond to messages addressed directly to the bot
        if full_text.startswith(self.bot_id):
            # Strip off the bot id and parse the rest of the message as the question
            question = full_text[len(self.bot_id):]
            if len(question) > 0:
                question = question.strip().lower()
                channel = event['channel']
                if 'list' in question:
                    self.respond(question, channel, f'I know about these graphs: {self.graph_shortcuts}')
                elif 'graph ' in question:
                    self.respond(question, channel, 'Please wait...', True)
                elif 'custom ' in question:
                    self.respond(question, channel, 'Please wait...', True)
                elif 'help' in question:
                    self.respond(question, channel, f'I can answer questions about: {self.help_msg}')
                elif 'bye' in question:
                    self.respond(question, channel, f'See ya')
                    raise SystemExit
                else:
                    self.respond(question, channel, f'Sorry, I cannot help you with that. Please try to ask `help`')

    def respond(self, question, channel, text, upload=False):
        if upload:
            graph_type = question.split()[0]
            graph_name = question.split()[1]
            if graph_type == "custom":
                graph_name = graph_name[1:-1]
                if '|' in unquote(graph_name):
                    graph_name = graph_name.split('|')[0]
                self.slack_client.api_call(
                    'chat.postMessage',
                    channel=channel,
                    text="custom: " + text,
                    as_user='true:')
                self.generate_and_upload_graph(graph_type, graph_name, channel)
            elif graph_type == "graph" and graph_name in self.graph_urls:
                self.slack_client.api_call(
                    'chat.postMessage',
                    channel=channel,
                    text=text,
                    as_user='true:')
                url = self.graph_urls[graph_name]
                self.generate_and_upload_graph(graph_name, url, channel)
            else:
                self.slack_client.api_call(
                    'chat.postMessage',
                    channel=channel,
                    text='graph does not exist',
                    as_user='true:')
        else:
            self.slack_client.api_call(
                'chat.postMessage',
                channel=channel,
                text=text,
                as_user='true:')



    def generate_and_upload_graph(self, filename, url, channel):
        # Create the graph in the current directory
        dir_name = os.path.dirname(os.path.abspath(__file__))

        puppetron = self.puppetron

        existing_files = prepare_dir(dir_name)

        dfile = random_number() + ".jpg"
        # print("Getting file")
        r = requests.get(puppetron + url, stream=True)
        if r.status_code == 200:
            with open(dfile, 'wb') as f:
                for chunk in r.iter_content():
                    f.write(chunk)
        else:
            self.slack_client.api_call(
                'chat.postMessage',
                channel=channel,
                text='Error getting the image. Try yourself at ' + puppetron + url ,
                as_user='true:')
            return
        # print("reading files")
        # Poll for new files
        while True:
            time.sleep(.5)
            new_files = os.listdir(dir_name)
            new = [f for f in new_files if all([f not in existing_files, f.endswith(".jpg")])]
            # print("uploading files")
            for f in new:
                with open(f, 'rb') as in_file:
                    ret = self.slack_client.api_call(
                        "files.upload",
                        filename=filename,
                        channels=channel,
                        title=filename,
                        file=io.BytesIO(in_file.read()))
                    if 'ok' not in ret or not ret['ok']:
                        print('File upload failed %s', ret['error'])
                os.remove(f)
            break
        # print("end of generate_and_upload_graph")


def random_number(size=10):
    _temp = ""
    for x in range(size):
        _temp = _temp + str(random.randint(100,999))
    return _temp

def prepare_dir(dir_name):
    # Check for any images from a previous run and remove them
    files_in_dir = os.listdir(dir_name)
    for item in files_in_dir:
        if item.endswith(".jpg"):
            os.remove(os.path.join(dir_name, item))
    return os.listdir(dir_name)


def configure(filename):
    if os.path.exists(filename) is False:
        raise IOError("{0} does not exist".format(filename))

    with open(filename) as config_file:
        config_data = yaml.load(config_file)

    return config_data


def main(arguments=None):
    if not arguments:
        arguments = docopt(__doc__)
    config = configure(arguments['--config-file'])
    mybot = SlackBot(config)
    mybot.start()


if __name__ == "__main__":
    main()
