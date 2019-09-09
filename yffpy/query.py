__author__ = "Wren J. R. (uberfastman)"
__email__ = "wrenjr@yahoo.com"

import json
import logging
import os

from yahoo_oauth import OAuth2

from yffpy.models import YahooFantasyObject, Game, User, League, Standings, Settings, Player
from yffpy.utils import reformat_json_list, unpack_data

logger = logging.getLogger(__name__)
# suppress yahoo-oauth debug logging
logging.getLogger("yahoo_oauth").setLevel(level=logging.INFO)


class YahooFantasyFootballQuery(object):
    """
    Yahoo fantasy football query to retrieve all types of FF data
    """

    def __init__(self, auth_dir, league_id, game_id=None, offline=False):
        """
        :param auth_dir: location of both private.json (containing Yahoo dev app consumer_key and consumer_secret) and
            token.json (generated by OAuth2 three-legged handshake)
        :param league_id: league id of selected Yahoo fantasy league
        :param game_id: game id of selected Yahoo fantasy football game corresponding to a specific year, and defaulting
            to the current year
        :param offline: boolean to run in offline mode (ONLY WORKS IF ALL NEEDED YAHOO FANTASY FOOTBALL DATA HAS BEEN
            PREVIOUSLY SAVED LOCALLY USING data.py)
        """

        self.league_id = league_id
        self.game_id = game_id
        self.league_key = None
        self.offline = offline

        if not self.offline:
            # load credentials
            with open(os.path.join(auth_dir, "private.json")) as yahoo_app_credentials:
                auth_info = json.load(yahoo_app_credentials)
            self._yahoo_consumer_key = auth_info["consumer_key"]
            self._yahoo_consumer_secret = auth_info["consumer_secret"]

            # load or create OAuth2 refresh token
            token_file_path = os.path.join(auth_dir, "token.json")
            if os.path.isfile(token_file_path):
                with open(token_file_path) as yahoo_oauth_token:
                    auth_info = json.load(yahoo_oauth_token)
            else:
                with open(token_file_path, "w") as yahoo_oauth_token:
                    json.dump(auth_info, yahoo_oauth_token)

            if "access_token" in auth_info.keys():
                self._yahoo_access_token = auth_info["access_token"]

            # complete OAuth2 3-legged handshake by either refreshing existing token or requesting account access and
            # returning a verification code to input to the command line prompt
            self.oauth = OAuth2(None, None, from_file=token_file_path)
            if not self.oauth.token_is_valid():
                self.oauth.refresh_access_token()

    def query(self, url, data_key_list, data_type_class=None):
        """
        :param url: web url for desired Yahoo fantasy football data
        :param data_key_list: list of keys used to extract the specific data desired by the given query
        :param data_type_class: highest level data model type (if one exists for the specific retrieved data
        :return: dictionary containing the cleaned data, the url used to retrieve the data, and the raw response data
        """

        if not self.offline:
            response = self.oauth.session.get(url, params={"format": "json"})
            logger.debug("RESPONSE (RAW JSON): {}".format(response.json()))
            raw_response_data = response.json().get("fantasy_content")
            logger.debug("RESPONSE (Yahoo fantasy football data extracted from: \"fantasy_content\"): {}".format(
                raw_response_data))

            for i in range(len(data_key_list)):
                if type(raw_response_data) == list:
                    raw_response_data = reformat_json_list(raw_response_data)[data_key_list[i]]
                else:
                    raw_response_data = raw_response_data.get(data_key_list[i])
            logger.debug("RESPONSE (Yahoo fantasy football data extracted from: {}): {}".format(data_key_list,
                                                                                                raw_response_data))

            # unpack, parse, and assign data types to all retrieved data content
            unpacked = unpack_data(raw_response_data, YahooFantasyObject)

            # cast highest level of data to type corresponding to query (if type exists)
            clean_response_data = data_type_class(unpacked) if data_type_class else unpacked
            logger.debug(
                "UNPACKED AND PARSED JSON (Yahoo fantasy football data wth parent type: {}): {}".format(data_type_class,
                                                                                                        unpacked))
            return {
                "data": clean_response_data,
                "url": url,
                "raw": raw_response_data
            }
        else:
            logger.error("CANNOT RUN YAHOO QUERY WHILE USING OFFLINE MODE!")

    def get_current_nfl_fantasy_game(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/game/nfl", ["game"], Game)

    def get_nfl_fantasy_game(self, game_id):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/game/" + str(game_id), ["game"], Game)

    def get_league_key(self):
        if not self.league_key:
            if self.game_id:
                return self.get_nfl_fantasy_game(self.game_id).get("data").game_key + ".l." + self.league_id
            else:
                logger.warning(
                    "No Yahoo Fantasy game id provided, defaulting to current NFL fantasy football season game id.")
                return self.get_current_nfl_fantasy_game().get("data").game_key + ".l." + self.league_id
        else:
            return self.league_key

    def get_user_game_history(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;codes=nfl/", ["users", "0", "user"],
            User)

    def get_user_league_history(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;codes=nfl/leagues/",
            ["users", "0", "user"], User)

    def get_overview(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/league/" + self.get_league_key() + "/", ["league"], League)

    def get_standings(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/league/" + self.get_league_key() + "/standings",
            ["league", "standings"], Standings)

    def get_settings(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/league/" + self.get_league_key() + "/settings",
            ["league", "settings"], Settings)

    def get_teams(self):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/league/" + self.get_league_key() + "/teams", ["league", "teams"])

    def get_matchups(self, chosen_week):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/league/" + self.get_league_key() + "/scoreboard;week=" +
            str(chosen_week), ["league", "scoreboard", "0", "matchups"])

    def get_team_roster(self, team_id, chosen_week):
        team_key = self.get_league_key() + ".t." + str(team_id)
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/team/" + str(team_key) + "/roster;week=" +
            str(chosen_week) + "/players/stats", ["team", "roster", "0", "players"])

    def get_player_stats(self, player_key, chosen_week):
        return self.query(
            "https://fantasysports.yahooapis.com/fantasy/v2/league/" + self.get_league_key() + "/players;player_keys=" +
            str(player_key) + "/stats;type=week;week=" + str(chosen_week), ["league", "players", "0", "player"], Player)
