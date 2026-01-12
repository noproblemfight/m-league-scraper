import json
import os
from datetime import datetime
from collections import defaultdict

def generate_html(all_player_data, draft_teams, team_colors):
    # --- データ集計 ---
    player_stats = defaultdict(lambda: {'total_score': 0.0, 'game_count': 0, 'rank_sum': 0})
    for _, player_name, score, rank in all_player_data:
        player_stats[player_name]['total_score'] += score
        player_stats[player_name]['game_count'] += 1
        player_stats[player_name]['rank_sum'] += rank

    team_totals = defaultdict(float)
    for team, members in draft_teams.items():
        for member in members:
            team_totals[team] += player_stats[member]['total_score']

    # 特別ルール適用 (configから読み直すのが理想だが、ここでは引数で渡されていないため簡易的に実装するか、
    # あるいはscraper側ですでに計算された値を渡すのがベター。
    # 今回は表示用なので、configを再度読み込む形にするのが安全)
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            special_rules = config.get('special_rules', {})
            
            # チームボーナス
            for team, bonus in special_rules.get('team_bonus', {}).items():
                if team in team_totals:
                    team_totals[team] += bonus
            
            # 個人ボーナス (表示用スコア計算のため)
            player_bonus = special_rules.get('player_bonus', {})
    except:
        player_bonus = {}

    sorted_teams = sorted(team_totals.items(), key=lambda x: x[1], reverse=True)
    
    # --- HTML生成 ---
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    
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
        
        /* チームランキング */
        .rankings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .team-card {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: transform 0.2s;
            border-top: 4px solid transparent;
        }}
        .team-card:hover {{
            transform: translateY(-5px);
        }}
        .team-rank {{
            font-size: 1.2rem;
            font-weight: bold;
            color: var(--text-sub);
        }}
        .team-name {{
            font-size: 1.5rem;
            font-weight: bold;
            margin: 10px 0;
        }}
        .team-score {{
            font-size: 2.5rem;
            font-weight: bold;
            text-align: right;
            color: var(--text-main);
        }}
        .team-members {{
            margin-top: 15px;
            font-size: 0.9rem;
            color: var(--text-sub);
            border-top: 1px solid #333;
            padding-top: 10px;
        }}

        /* グラフエリア */
        .chart-container {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 40px;
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
        table {{
            width: 100%;
            border-collapse: collapse;
            white-space: nowrap;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #333;
        }}
        th {{
            color: var(--accent);
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #2a2a2a;
        }}
        .positive {{ color: #4CAF50; }}
        .negative {{ color: #FF5252; }}

        /* フッター */
        footer {{
            text-align: center;
            margin-top: 40px;
            color: var(--text-sub);
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>M-League Dashboard</h1>
            <div class="timestamp">Last Updated: {now_str}</div>
        </header>

        <section>
            <h2 style="border-left: 4px solid var(--accent); padding-left: 10px;">Team Ranking</h2>
            <div class="rankings-grid">
    """

    for i, (team, score) in enumerate(sorted_teams, 1):
        color_data = team_colors.get(team, {'red': 1, 'green': 1, 'blue': 1})
        # RGB値をCSS用に変換 (少し暗くして背景に馴染ませるか、アクセントにするか)
        # ここではborder-topの色として使用
        r, g, b = int(color_data['red']*255), int(color_data['green']*255), int(color_data['blue']*255)
        border_color = f"rgb({r},{g},{b})"
        
        members_str = " / ".join(draft_teams[team])
        score_class = "positive" if score >= 0 else "negative"
        score_fmt = f"{score:+.1f}"

        html += f"""
                <div class="team-card" style="border-top-color: {border_color};">
                    <div class="team-rank">#{i}</div>
                    <div class="team-name">{team}</div>
                    <div class="team-score {score_class}">{score_fmt}</div>
                    <div class="team-members">{members_str}</div>
                </div>
        """

    html += """
            </div>
        </section>

        <section>
            <h2 style="border-left: 4px solid var(--accent); padding-left: 10px;">Score History</h2>
            <div class="chart-container">
                <canvas id="scoreChart"></canvas>
            </div>
        </section>

        <section>
            <h2 style="border-left: 4px solid var(--accent); padding-left: 10px;">Player Stats</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Player</th>
                            <th>Team</th>
                            <th>Total Score</th>
                            <th>Games</th>
                            <th>Avg Rank</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    # 個人成績のリスト作成
    player_data_list = []
    # チーム所属選手のみを対象にする
    valid_players = set()
    for players in draft_teams.values():
        valid_players.update(players)

    for player, stats in player_stats.items():
        if player not in valid_players:
            continue
            
        final_score = stats['total_score'] + player_bonus.get(player, 0.0)
        avg_rank = stats['rank_sum'] / stats['game_count'] if stats['game_count'] > 0 else 0
        
        # 所属チームを探す
        team_name = "Unknown"
        for t, members in draft_teams.items():
            if player in members:
                team_name = t
                break
        
        player_data_list.append({
            'name': player,
            'team': team_name,
            'score': final_score,
            'games': stats['game_count'],
            'avg_rank': avg_rank
        })

    # スコア順にソート
    player_data_list.sort(key=lambda x: x['score'], reverse=True)

    for i, p in enumerate(player_data_list, 1):
        score_class = "positive" if p['score'] >= 0 else "negative"
        html += f"""
                        <tr>
                            <td>{i}</td>
                            <td>{p['name']}</td>
                            <td>{p['team']}</td>
                            <td class="{score_class}">{p['score']:+.1f}</td>
                            <td>{p['games']}</td>
                            <td>{p['avg_rank']:.2f}</td>
                        </tr>
        """

    html += """
                    </tbody>
                </table>
            </div>
        </section>

        <footer>
            Generated by M-League Scraper | Automagically updated via GitHub Actions
        </footer>
    </div>

    <script>
        // グラフ描画用データ (Scraperから渡すのが難しいので、ここでは簡易的にJSに埋め込むデータを生成する必要がありますが、
        // 過去の推移データを持っていないと描画できません。
        // 今回は「現在のトータルスコア」の棒グラフ、または簡易的な実装としておきます。
        // ※本来は daily_history.csv などを保存して読み込む必要がありますが、
        //   今回は要件をシンプルにするため、チームごとの現在スコア比較チャートにします。
        
        const ctx = document.getElementById('scoreChart').getContext('2d');
        const labels = [];
        const data = [];
        const bgColors = [];
        const borderColors = [];
    """
    
    # チャート用データ生成
    for team, score in sorted_teams:
        color_data = team_colors.get(team, {'red': 1, 'green': 1, 'blue': 1})
        r, g, b = int(color_data['red']*255), int(color_data['green']*255), int(color_data['blue']*255)
        
        html += f"labels.push('{team}');\n"
        html += f"data.push({score});\n"
        html += f"bgColors.push('rgba({r}, {g}, {b}, 0.5)');\n"
        html += f"borderColors.push('rgba({r}, {g}, {b}, 1)');\n"

    html += """
        const myChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Score',
                    data: data,
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#333' }
                    },
                    x: {
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    </script>
</body>
</html>
    """

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Web Page generated: {output_path}")

if __name__ == "__main__":
    # Test execution
    pass
