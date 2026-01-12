import os
import re
import time
import csv
import gspread
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
# gspread-formattingに必要な部品をすべてインポート
from gspread_formatting import CellFormat, Color, TextFormat, format_cell_range, format_cell_ranges
import mleague_viewer

import os
import re
import time
import csv
import json
import gspread
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
# gspread-formattingに必要な部品をすべてインポート
from gspread_formatting import CellFormat, Color, TextFormat, format_cell_range, format_cell_ranges

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_scraper(log_callback=print):
    try:
        config = load_config()
        
        SEASON_START_YEAR = config['season_start_year']
        urls = config['urls']
        spreadsheet_name = config['spreadsheet_name']
        output_filename = config['output_filename']
        SERVICE_ACCOUNT_FILE = config['service_account_file']
        DRAFT_TEAMS = config['draft_teams']
        TEAM_COLORS_CONFIG = config.get('team_colors', {})
        SPECIAL_RULES = config.get('special_rules', {})
        M_LEAGUE_PLAYERS = sorted(list(set(config['m_league_players'])))
        
        # ▼▼▼▼▼【重要】Google Driveを操作するための権限を再度追加します ▼▼▼▼▼
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        # ▲▲▲▲▲【重要】Google Driveを操作するための権限を再度追加します ▲▲▲▲▲

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # === STEP 1: スクレイピング処理 ===
        log_callback("STEP 1: スクレイピングを開始します...")
        raw_player_data = []
        try:
            for url in urls:
                log_callback(f"  処理中: {url}")
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')

                game_columns = soup.find_all('div', class_='p-gamesResult__column')

                for column in game_columns:
                    date_block = column.find_previous('div', class_='p-gamesResult__date')
                    date_text_raw = date_block.get_text(strip=True).split('(')[0] if date_block else "日付不明"
                    
                    try:
                        month, day = map(int, date_text_raw.split('/'))
                        year = SEASON_START_YEAR + 1 if month <= 5 else SEASON_START_YEAR
                        full_date_str = f"{year}/{month:02}/{day:02}"
                    except (ValueError, IndexError):
                        full_date_str = date_text_raw

                    number_tag = column.find('div', class_='p-gamesResult__number')
                    number_text = number_tag.get_text(strip=True) if number_tag else "回戦不明"
                    unique_game_title = f"{full_date_str} {number_text}"
                    
                    rank_list = column.find('ol', class_='p-gamesResult__rank-list')
                    if not rank_list:
                        continue

                    player_list_items = rank_list.find_all('li')
                    
                    for rank, item in enumerate(player_list_items, 1):
                        name_tag = item.find('div', class_='p-gamesResult__name')
                        point_tag = item.find('div', class_='p-gamesResult__point')
                        if name_tag and point_tag:
                            player_name = name_tag.get_text(strip=True)
                            point_text = point_tag.get_text(strip=True)
                            
                            temp_str = point_text.replace('▲', '-')
                            point_value_str = re.sub(r'[^-0-9.]', '', temp_str)
                            
                            try:
                                if point_value_str and point_value_str != '-':
                                    point_as_float = float(point_value_str)
                                    raw_player_data.append([unique_game_title, player_name, point_as_float, rank])
                            except (ValueError, TypeError):
                                pass

            log_callback("STEP 1: スクレイピングが完了しました。\n")
        except Exception as e:
            log_callback(f"  STEP 1でエラーが発生しました: {e}\n")
            # スクレイピング失敗時は続行不可とするか、あるいは既存データだけで動くかだが、
            # 元のロジックでは raw_player_data=[] にして続行しているのでそれに従う
            raw_player_data = []


        # === STEP 1.5: 重複データの削除 ===
        all_player_data = []
        if raw_player_data:
            log_callback("STEP 1.5: 重複データの削除処理を開始します...")
            
            games_raw = defaultdict(list)
            for game_data in raw_player_data:
                games_raw[game_data[0]].append(game_data)
                
            processed_games = set()

            for game_title, all_entries_for_title in games_raw.items():
                for i in range(0, len(all_entries_for_title), 4):
                    single_game_data = all_entries_for_title[i:i+4]
                    
                    if len(single_game_data) == 4:
                        player_names_in_game = sorted([p[1] for p in single_game_data])
                        game_key = (game_title, tuple(player_names_in_game))

                        if game_key not in processed_games:
                            all_player_data.extend(single_game_data)
                            processed_games.add(game_key)

            log_callback(f"  重複削除後のデータ件数: {len(all_player_data)}件\n")


        # === STEP 2: ローカルにCSVファイルとして保存 ===
        if all_player_data:
            log_callback(f"STEP 2: データをローカルファイル '{output_filename}' に保存します...")
            header = ['試合', '選手名', 'スコア', '順位']
            sorted_data = sorted(all_player_data, key=lambda x: x[0])
            with open(output_filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(sorted_data)
            log_callback("STEP 2: ローカルへの保存が完了しました。\n")
        else:
            log_callback("STEP 2: 有効なデータが取得できませんでした。\n")


        # === STEP 3: Googleへの認証 ===
        creds = None
        if all_player_data:
            log_callback("STEP 3: Googleへの認証情報を読み込みます...")
            try:
                # 1. まずローカルファイルを確認
                if os.path.exists(SERVICE_ACCOUNT_FILE):
                    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
                    log_callback(f"STEP 3: ローカルファイル({SERVICE_ACCOUNT_FILE})での認証が成功しました。\n")
                
                # 2. ファイルがない場合、環境波数を確認 (クラウド用)
                elif 'GOOGLE_CREDENTIALS_JSON' in os.environ:
                    log_callback("  ローカルファイルが見つかりません。環境変数から認証情報を読み込みます...")
                    service_account_info = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
                    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
                    log_callback("STEP 3: 環境変数での認証が成功しました。\n")
                
                else:
                    raise FileNotFoundError(f"認証ファイル({SERVICE_ACCOUNT_FILE})も環境変数(GOOGLE_CREDENTIALS_JSON)も見つかりません。")

            except Exception as e:
                log_callback(f"  認証情報の読み込みに失敗しました: {e}")
                log_callback("  設定を確認してください。")


        # === STEP 4: スプレッドシートへの書き込み処理 ===
        if creds:
            try:
                log_callback("STEP 4: スプレッドシートへの書き込み処理を開始します...")
                gc = gspread.authorize(creds)
                sh = gc.open(spreadsheet_name)

                default_format = CellFormat(
                    backgroundColor=Color(1, 1, 1),
                    textFormat=TextFormat(bold=False)
                )

                # --- 4-1: 「試合結果」シートの更新 ---
                log_callback("  4-1: 「試合結果」シートを更新中...")
                player_to_team = {player: team for team, players in DRAFT_TEAMS.items() for player in players}
                
                team_colors = {}
                for team_name, color_data in TEAM_COLORS_CONFIG.items():
                    team_colors[team_name] = Color(color_data['red'], color_data['green'], color_data['blue'])
                
                # 色設定がないチームのためにデフォルト値を設定 (白)
                for team_name in DRAFT_TEAMS.keys():
                    if team_name not in team_colors:
                        team_colors[team_name] = Color(1, 1, 1)

                games = defaultdict(list)
                for game_title, player_name, score, rank in all_player_data:
                    games[game_title].append({'name': player_name, 'score': score, 'rank': rank})

                unique_games = []
                for game_title, players_data in games.items():
                    for i in range(0, len(players_data), 4):
                        game_chunk = players_data[i:i+4]
                        if len(game_chunk) == 4:
                            unique_games.append((game_title, game_chunk))

                legend_row = ['凡例:'] + list(DRAFT_TEAMS.keys())
                header_games = ['試合', '1位', '2位', '3位', '4位']
                data_games = [legend_row, header_games]
                color_formats = []

                sorted_unique_games = sorted(unique_games, key=lambda x: x[0], reverse=True)
                for row_idx, (game_title, players_in_game) in enumerate(sorted_unique_games, 3):
                    sorted_players = sorted(players_in_game, key=lambda p: p['rank'])
                    row_to_write = [game_title]
                    
                    for player_info in sorted_players:
                        player_name = player_info['name']
                        score = player_info['score']
                        score_str = f"({'+' if score >= 0 else ''}{round(score, 1)})"
                        display_text = f"{player_name} {score_str}"
                        row_to_write.append(display_text)
                    
                    row_to_write.extend([''] * (5 - len(row_to_write)))
                    data_games.append(row_to_write[:5])

                try:
                    worksheet_games = sh.worksheet("試合結果")
                except gspread.WorksheetNotFound:
                    worksheet_games = sh.add_worksheet(title="試合結果", rows=len(data_games)+10, cols=5)

                worksheet_games.clear()
                worksheet_games.update(data_games, value_input_option='USER_ENTERED')
                
                format_cell_range(worksheet_games, 'A1:Z1000', default_format)
                
                for i, team_name in enumerate(DRAFT_TEAMS.keys(), 2):
                    color_formats.append((gspread.utils.rowcol_to_a1(1, i), CellFormat(backgroundColor=team_colors.get(team_name))))

                for row_idx, (game_title, players_in_game) in enumerate(sorted_unique_games, 3):
                    sorted_players = sorted(players_in_game, key=lambda p: p['rank'])
                    for player_info in sorted_players:
                        rank = player_info['rank']
                        player_name = player_info['name']
                        col_idx = rank + 1
                        cell_label = gspread.utils.rowcol_to_a1(row_idx, col_idx)
                        if player_name in player_to_team:
                            team_name = player_to_team[player_name]
                            color_formats.append((cell_label, CellFormat(backgroundColor=team_colors.get(team_name))))
                
                if color_formats:
                    format_cell_ranges(worksheet_games, color_formats)
                
                # --- 4-2: 「チーム別スコア内訳」シートの作成・更新 ---
                log_callback("  4-2: 「チーム別スコア内訳」シートを更新中...")
                
                player_stats = defaultdict(lambda: {'total_score': 0.0, 'game_count': 0, 'rank_sum': 0})
                
                for _, player_name, score, rank in all_player_data:
                    player_stats[player_name]['total_score'] += score
                    player_stats[player_name]['game_count'] += 1
                    player_stats[player_name]['rank_sum'] += rank

                team_totals = defaultdict(float)
                for team, members in DRAFT_TEAMS.items():
                    for member in members:
                        team_totals[team] += player_stats[member]['total_score']

                # 特別ルール: チームボーナス
                team_bonus = SPECIAL_RULES.get('team_bonus', {})
                for team, bonus in team_bonus.items():
                    if team in team_totals:
                        team_totals[team] += bonus
                
                now = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
                data_details = [[f"最終更新日時: {now}"], []]
                
                data_details.append(["チーム総合ランキング"])
                data_details.append(["順位", "チーム名", "合計スコア"])
                sorted_teams = sorted(team_totals.items(), key=lambda item: item[1], reverse=True)
                
                for i, (team_name, total_score) in enumerate(sorted_teams, 1):
                    data_details.append([f"{i}位", team_name, round(total_score, 1)])
                data_details.append([])
                
                data_details.append(["選手別 詳細成績"])
                header_players = ["所属チーム", "選手名", "個人合計スコア", "平均順位", "出場回数"]
                data_details.append(header_players)
                
                color_formats_list_details = []
                
                player_bonus = SPECIAL_RULES.get('player_bonus', {})

                for team_name, players in DRAFT_TEAMS.items():
                    for player in players:
                        stats = player_stats[player]
                        player_display_score = stats['total_score']
                        
                        # 特別ルール: 個人ボーナス
                        if player in player_bonus:
                            player_display_score += player_bonus[player]
                        
                        avg_rank = round(stats['rank_sum'] / stats['game_count'], 2) if stats['game_count'] > 0 else 0
                        data_details.append([team_name, player, round(player_display_score, 1), avg_rank, stats['game_count']])
                    
                    data_details.append([f"{team_name} 合計", "", round(team_totals[team_name], 1), "", ""])
                    
                    total_row_num = len(data_details)
                    total_row_color_format = CellFormat(backgroundColor=team_colors.get(team_name))
                    color_formats_list_details.append((f'A{total_row_num}:E{total_row_num}', total_row_color_format))
                    
                    data_details.append([])

                try:
                    worksheet_details = sh.worksheet("チーム別スコア内訳")
                except gspread.WorksheetNotFound:
                    worksheet_details = sh.add_worksheet(title="チーム別スコア内訳", rows=1, cols=1)
                
                worksheet_details.clear()
                worksheet_details.update(data_details, value_input_option='USER_ENTERED')
                
                # --- 4-3: 書式設定 ---
                log_callback("  4-3: 書式を設定中...")
                
                format_cell_range(worksheet_details, 'A1:Z1000', default_format)
                
                team_to_rank_row = {team_name: i + 5 for i, (team_name, _) in enumerate(sorted_teams)}
                for team_name, row_num in team_to_rank_row.items():
                    color_formats_list_details.append((f'B{row_num}', CellFormat(backgroundColor=team_colors.get(team_name))))

                if color_formats_list_details:
                    format_cell_ranges(worksheet_details, color_formats_list_details)
                
                # --- 4-4: 「スコア推移グラフ用データ」シートの更新 ---
                log_callback("  4-4: 「スコア推移グラフ用データ」シートを更新中...")
                
                games_team_scores = defaultdict(lambda: defaultdict(float))
                for game_title, player_name, score, _ in all_player_data:
                    for team, members in DRAFT_TEAMS.items():
                        if player_name in members:
                            games_team_scores[game_title][team] += score

                chart_data = []
                team_order = list(DRAFT_TEAMS.keys())
                header_chart = ['試合'] + team_order
                chart_data.append(header_chart)

                cumulative_scores = {team: 0.0 for team in team_order}
                
                # 特別ルール: 開幕前スコア (チームボーナス)
                team_bonus = SPECIAL_RULES.get('team_bonus', {})
                for team, bonus in team_bonus.items():
                    if team in cumulative_scores:
                        cumulative_scores[team] = bonus

                chart_data.append(['開幕前'] + [round(s, 1) for s in cumulative_scores.values()])
                
                for game_title in sorted(games_team_scores.keys()):
                    for team_name in team_order:
                        cumulative_scores[team_name] += games_team_scores[game_title].get(team_name, 0.0)
                    
                    row = [game_title] + [round(cumulative_scores[team], 1) for team in team_order]
                    chart_data.append(row)

                try:
                    worksheet_chart = sh.worksheet("スコア推移グラフ用データ")
                except gspread.WorksheetNotFound:
                    worksheet_chart = sh.add_worksheet(title="スコア推移グラフ用データ", rows=1, cols=1)
                    
                worksheet_chart.clear()
                worksheet_chart.update(chart_data, value_input_option='USER_ENTERED')
                
                # --- 4-5: 「個人ランキング」シートの作成・更新 ---
                log_callback("  4-5: 「個人ランキング」シートを更新中...")

                all_player_stats_for_ranking = defaultdict(lambda: {
                    'total_score': 0.0,
                    'ranks': {1: 0, 2: 0, 3: 0, 4: 0}
                })
                
                for _, player_name, score, rank in all_player_data:
                    if player_name in M_LEAGUE_PLAYERS:
                        all_player_stats_for_ranking[player_name]['total_score'] += score
                        if rank in [1, 2, 3, 4]:
                            all_player_stats_for_ranking[player_name]['ranks'][rank] += 1
                
                ranking_data = []
                for player_name in M_LEAGUE_PLAYERS:
                    stats = all_player_stats_for_ranking[player_name]
                    ranking_data.append([
                        player_name, 
                        stats['total_score'], 
                        stats['ranks'][1], 
                        stats['ranks'][2], 
                        stats['ranks'][3], 
                        stats['ranks'][4]
                    ])
                    
                sorted_ranking = sorted(ranking_data, key=lambda x: x[1], reverse=True)

                data_for_ranking_sheet = [["順位", "選手名", "合計スコア", "1位", "2位", "3位", "4位"]]
                ranking_color_formats = []

                for i, (player_name, total_score, r1, r2, r3, r4) in enumerate(sorted_ranking, 1):
                    data_for_ranking_sheet.append([f"{i}位", player_name, round(total_score, 1), r1, r2, r3, r4])
                    
                    if player_name in player_to_team:
                        team_name = player_to_team[player_name]
                        cell_format = CellFormat(backgroundColor=team_colors.get(team_name))
                        ranking_color_formats.append((f'A{i+1}:G{i+1}', cell_format))

                try:
                    worksheet_ranking = sh.worksheet("個人ランキング")
                except gspread.WorksheetNotFound:
                    worksheet_ranking = sh.add_worksheet(title="個人ランキング", rows=len(M_LEAGUE_PLAYERS) + 5, cols=7)
                
                worksheet_ranking.clear()
                worksheet_ranking.update(data_for_ranking_sheet, value_input_option='USER_ENTERED')
                
                format_cell_range(worksheet_ranking, 'A1:Z1000', default_format)
                if ranking_color_formats:
                    format_cell_ranges(worksheet_ranking, ranking_color_formats)

                # --- 4-6: 全シートの列幅を自動調整 ---
                log_callback("  4-6: 全シートの列幅を自動調整中...")
                requests_body = {
                    'requests': [
                        {'autoResizeDimensions': {'dimensions': { 'sheetId': worksheet_games.id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 5 }}},
                        {'autoResizeDimensions': {'dimensions': { 'sheetId': worksheet_details.id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 5 }}},
                        {'autoResizeDimensions': {'dimensions': { 'sheetId': worksheet_chart.id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': len(DRAFT_TEAMS) + 1 }}},
                        {'autoResizeDimensions': {'dimensions': { 'sheetId': worksheet_ranking.id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 7 }}}
                    ]
                }
                sh.batch_update(requests_body)
                    
                log_callback("STEP 4: すべてのスプレッドシートの更新が完了しました。\n")

            except Exception as e:
                log_callback(f"  STEP 4でエラーが発生しました: {e}\n")

        # === STEP 5: Webページ生成 ===
        if all_player_data:
            try:
                log_callback("STEP 5: Webページ(index.html)を生成します...")
                
                # 色設定の構築
                team_colors = {}
                for team_name, color_data in TEAM_COLORS_CONFIG.items():
                    team_colors[team_name] = color_data
                
                mleague_viewer.generate_html(all_player_data, DRAFT_TEAMS, team_colors)
                log_callback("STEP 5: 生成が完了しました。\n")
                
            except Exception as e:
                log_callback(f"  STEP 5でエラーが発生しました: {e}\n")

        log_callback("すべての処理が完了しました。")

    except Exception as e:
        log_callback(f"予期せぬエラーが発生しました: {e}")

if __name__ == "__main__":
    run_scraper()

