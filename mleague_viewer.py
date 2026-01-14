import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

def generate_html(all_player_data, draft_teams, team_colors):
    # --- 1. データ集計 (最終スコア & 直近日差分) ---
    player_stats = defaultdict(lambda: {'total_score': 0.0, 'game_count': 0, 'rank_sum': 0, 'day_diff': 0.0})
    team_totals = defaultdict(float)
    team_day_diffs = defaultdict(float)

    # 日付リストを取得して最新の日付を特定
    all_dates = sorted(list(set([d[0].split(' ')[0] for d in all_player_data])))
    last_date = all_dates[-1] if all_dates else None

    for game_title, player_name, score, rank in all_player_data:
        # トータル集計
        player_stats[player_name]['total_score'] += score
        player_stats[player_name]['game_count'] += 1
        player_stats[player_name]['rank_sum'] += rank
        
        # 直近日差分集計
        game_date = game_title.split(' ')[0]
        if game_date == last_date:
            player_stats[player_name]['day_diff'] += score

    # チーム集計
    for team, members in draft_teams.items():
        for member in members:
            team_totals[team] += player_stats[member]['total_score']
            team_day_diffs[team] += player_stats[member]['day_diff']

    sorted_teams = sorted(team_totals.items(), key=lambda x: x[1], reverse=True)
    
    # --- 2. 時系列データの作成 (グラフ用) ---
    games_map = defaultdict(list)
    for game_title, player_name, score, rank in all_player_data:
        games_map[game_title].append({'name': player_name, 'score': score})
    
    history_dates = ['開幕前']
    team_history = {team: [0.0] for team in draft_teams.keys()}
    current_team_scores = {team: 0.0 for team in draft_teams.keys()}
    
    # 試合順に処理
    for game_title, players in games_map.items():
        history_dates.append(game_title.split(' ')[0])
        
        for p in players:
            for team, members in draft_teams.items():
                if p['name'] in members:
                    current_team_scores[team] += p['score']
                    break
        
        for team in draft_teams.keys():
            team_history[team].append(round(current_team_scores[team], 1))

    # --- 3. サンプルチーム用データ ---
    all_players_info = []
    for player_name, stats in player_stats.items():
        all_players_info.append({
            'name': player_name,
            'score': round(stats['total_score'], 1)
        })
    all_players_info.sort(key=lambda x: x['score'], reverse=True)


    # --- 4. HTML生成 ---
    # 日本時間 (UTC+9)
    jst_now = datetime.utcnow() + timedelta(hours=9)
    now_str = jst_now.strftime('%Y/%m/%d %H:%M')
    
    html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>M-League Scraper Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Nota+Sans+JP:wght@400;700&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #121212;
            --card-bg: #1e1e1e;
            --text-main: #ffffff;
            --text-sub: #b0b0b0;
            --accent: #d4af37; /* Gold */
        }}
        body {{
            font-family: 'Roboto', 'Noto Sans JP', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid #333;
        }}
        h1 {{
            font-size: 2.5rem;
            margin: 0;
            color: var(--accent);
        }}
        .timestamp {{
            color: var(--text-sub);
            font-size: 0.9rem;
            margin-top: 5px;
        }}
        
        section {{
            margin-bottom: 60px;
        }}
        h2 {{
            border-left: 4px solid var(--accent);
            padding-left: 10px;
            margin-bottom: 20px;
        }}

        /* チームランキング */
        .rankings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        .team-card {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border-top: 4px solid transparent;
        }}
        .team-rank {{ font-size: 1.2rem; font-weight: bold; color: var(--text-sub); }}
        .team-name {{ font-size: 1.5rem; font-weight: bold; margin: 10px 0; }}
        .team-score {{ font-size: 2.5rem; font-weight: bold; text-align: right; }}
        .team-diff {{ font-size: 1rem; text-align: right; margin-top: -5px; margin-bottom: 10px; }}
        .team-members {{ margin-top: 15px; font-size: 0.9rem; color: var(--text-sub); border-top: 1px solid #333; padding-top: 10px; }}

        /* グラフエリア */
        .chart-container {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            height: 400px;
            position: relative;
        }}

        /* 個人成績テーブル */
        .table-container {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            overflow-x: auto;
        }}
        table {{ width: 100%; border-collapse: collapse; white-space: nowrap; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: var(--accent); font-weight: bold; }}
        tr:hover {{ background-color: #2a2a2a; }}
        .positive {{ color: #4CAF50; }}
        .negative {{ color: #FF5252; }}
        .diff-text {{ font-size: 0.8rem; margin-left: 5px; }}

        /* サンプルチーム (My Team) */
        .sample-team-container {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
        }}
        .selectors-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .selector-item {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        select {{
            width: 100%;
            padding: 10px;
            background-color: #333;
            color: white;
            border: 1px solid #555;
            border-radius: 6px;
            font-size: 1rem;
        }}
        .player-score-display {{
            text-align: right;
            font-size: 0.9rem;
            min-height: 1.2em;
            font-weight: bold;
        }}
        .my-team-result {{
            text-align: center;
            border-top: 1px solid #444;
            padding-top: 20px;
        }}
        .my-total-label {{ font-size: 1.2rem; color: var(--text-sub); }}
        .my-total-score {{ font-size: 3rem; font-weight: bold; color: var(--accent); }}

        footer {{ text-align: center; margin-top: 40px; color: var(--text-sub); font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>M-League Dashboard</h1>
            <div class="timestamp">Last Updated: {now_str} (JST)</div>
        </header>

        <!-- 1. チームランキング -->
        <section>
            <h2>Team Ranking</h2>
            <div class="rankings-grid">
    """

    for i, (team, score) in enumerate(sorted_teams, 1):
        color_data = team_colors.get(team, {'red': 1, 'green': 1, 'blue': 1})
        r, g, b = int(color_data['red']*255), int(color_data['green']*255), int(color_data['blue']*255)
        border_color = f"rgb({r},{g},{b})"
        
        members_str = " / ".join(draft_teams.get(team, []))
        score_class = "positive" if score >= 0 else "negative"
        score_fmt = f"{score:+.1f}"

        # 差分表示
        diff = team_day_diffs[team]
        if diff != 0:
            diff_sign = "+" if diff > 0 else ""
            diff_color = "#4CAF50" if diff > 0 else "#FF5252"
            diff_html = f'<span style="color: {diff_color};">({last_date}: {diff_sign}{diff:.1f})</span>'
        else:
            diff_html = '<span style="color: #555;">(-)</span>'

        html += f"""
                <div class="team-card" style="border-top-color: {border_color};">
                    <div class="team-rank">#{i}</div>
                    <div class="team-name">{team}</div>
                    <div class="team-score {score_class}">{score_fmt}</div>
                    <div class="team-diff">{diff_html}</div>
                    <div class="team-members">{members_str}</div>
                </div>
        """

    html += """
            </div>
        </section>

        <!-- 2. スコア推移グラフ -->
        <section>
            <h2>Score History</h2>
            <div class="chart-container">
                <canvas id="historyChart"></canvas>
            </div>
        </section>

        <!-- 3. 個人成績 -->
        <section>
            <h2>Player Stats</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Player</th>
                            <th>Team</th>
                            <th>Total Score</th>
                            <th>Last Game</th>
                            <th>Games</th>
                            <th>Avg Rank</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    player_data_list = []
    valid_players = set()
    for players in draft_teams.values():
        valid_players.update(players)

    for player, stats in player_stats.items():
        if player not in valid_players:
            continue
            
        final_score = stats['total_score']
        avg_rank = stats['rank_sum'] / stats['game_count'] if stats['game_count'] > 0 else 0
        
        team_name = "Unknown"
        for t, members in draft_teams.items():
            if player in members:
                team_name = t
                break
        
        player_data_list.append({
            'name': player,
            'team': team_name,
            'score': final_score,
            'diff': stats['day_diff'],
            'games': stats['game_count'],
            'avg_rank': avg_rank
        })

    player_data_list.sort(key=lambda x: x['score'], reverse=True)

    for i, p in enumerate(player_data_list, 1):
        score_class = "positive" if p['score'] >= 0 else "negative"
        
        # 個人差分
        if p['diff'] != 0:
            diff_sign = "+" if p['diff'] > 0 else ""
            diff_color = "positive" if p['diff'] > 0 else "negative"
            diff_html = f'<span class="{diff_color} diff-text">({diff_sign}{p["diff"]:.1f})</span>'
        else:
            diff_html = '<span style="color: #555; font-size: 0.8rem;">-</span>'

        html += f"""
                        <tr>
                            <td>{i}</td>
                            <td>{p['name']}</td>
                            <td>{p['team']}</td>
                            <td class="{score_class}">{p['score']:+.1f}</td>
                            <td>{diff_html}</td>
                            <td>{p['games']}</td>
                            <td>{p['avg_rank']:.2f}</td>
                        </tr>
        """

    html += """
                    </tbody>
                </table>
            </div>
        </section>

        <!-- 4. サンプルチーム作成 (一番下に移動) -->
        <section>
            <h2>Create Your Sample Team</h2>
            <div class="sample-team-container">
                <p style="color: #aaa; margin-bottom: 15px;">好きな選手を4人選んで、シミュレーションチームの合計スコアを計算できます。</p>
                <div class="selectors-grid">
                    <div class="selector-item">
                        <select id="p1" onchange="calculateMyTeam()"><option value="0">Select Player 1</option></select>
                        <div id="s1" class="player-score-display"></div>
                    </div>
                    <div class="selector-item">
                        <select id="p2" onchange="calculateMyTeam()"><option value="0">Select Player 2</option></select>
                        <div id="s2" class="player-score-display"></div>
                    </div>
                    <div class="selector-item">
                        <select id="p3" onchange="calculateMyTeam()"><option value="0">Select Player 3</option></select>
                        <div id="s3" class="player-score-display"></div>
                    </div>
                    <div class="selector-item">
                        <select id="p4" onchange="calculateMyTeam()"><option value="0">Select Player 4</option></select>
                        <div id="s4" class="player-score-display"></div>
                    </div>
                </div>
                <div class="my-team-result">
                    <div class="my-total-label">Estimated Total Score</div>
                    <div class="my-total-score" id="myScore">0.0</div>
                </div>
            </div>
        </section>

        <footer>
            Generated by M-League Scraper | Automagically updated via GitHub Actions
        </footer>
    </div>

    <script>
        // --- データ埋め込み ---
    """

    html += f"const labels = {json.dumps(history_dates, ensure_ascii=False)};\n"
    html += "const datasets = [\n"
    
    for team, scores in team_history.items():
        color_data = team_colors.get(team, {'red': 1, 'green': 1, 'blue': 1})
        r, g, b = int(color_data['red']*255), int(color_data['green']*255), int(color_data['blue']*255)
        
        html += "{\n"
        html += f"  label: '{team}',\n"
        html += f"  data: {scores},\n"
        html += f"  borderColor: 'rgba({r}, {g}, {b}, 1)',\n"
        html += f"  backgroundColor: 'rgba({r}, {g}, {b}, 1)',\n"
        html += "  borderWidth: 2,\n"
        html += "  tension: 0.1,\n"
        html += "  pointRadius: 0,\n"
        html += "  pointHoverRadius: 5\n"
        html += "},\n"
    
    html += "];\n"

    html += f"const playerMap = {json.dumps(all_players_info, ensure_ascii=False)};\n"

    html += """
        // --- グラフ描画 ---
        const ctx = document.getElementById('historyChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        grid: { color: '#333' },
                        ticks: { color: '#aaa' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#aaa' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff' }
                    }
                }
            }
        });

        // --- サンプルチーム計算 ---
        const selects = [
            document.getElementById('p1'),
            document.getElementById('p2'),
            document.getElementById('p3'),
            document.getElementById('p4')
        ];
        const scoreDisplays = [
            document.getElementById('s1'),
            document.getElementById('s2'),
            document.getElementById('s3'),
            document.getElementById('s4')
        ];

        // セレクトボックス初期化 (名前だけ表示、スコアは隠す)
        playerMap.forEach(p => {
            const optionText = p.name; 
            selects.forEach(sel => {
                const opt = document.createElement('option');
                opt.value = p.score;
                opt.textContent = optionText;
                sel.appendChild(opt);
            });
        });

        function calculateMyTeam() {
            let total = 0.0;
            selects.forEach((sel, index) => {
                const val = parseFloat(sel.value);
                const display = scoreDisplays[index];
                total += val;
                
                // 個別スコアの表示切り替え
                if (sel.selectedIndex > 0) { // 選手が選ばれているとき
                     const sign = val > 0 ? '+' : '';
                     display.textContent = `${sign}${val.toFixed(1)}`;
                     display.style.color = val >= 0 ? '#4CAF50' : '#FF5252';
                } else {
                     display.textContent = '';
                }
            });
            
            const totalDisplay = document.getElementById('myScore');
            totalDisplay.textContent = (total > 0 ? '+' : '') + total.toFixed(1);
            
            if (total >= 0) {
                totalDisplay.style.color = '#4CAF50';
            } else {
                totalDisplay.style.color = '#FF5252';
            }
        }
    </script>
</body>
</html>
    """

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Web Page generated: {output_path}")

if __name__ == "__main__":
    pass
