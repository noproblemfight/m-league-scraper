import json
import os
from datetime import datetime
from collections import defaultdict

def generate_html(all_player_data, draft_teams, team_colors):
    # --- 1. データ集計 (最終スコア) ---
    player_stats = defaultdict(lambda: {'total_score': 0.0, 'game_count': 0, 'rank_sum': 0})
    for _, player_name, score, rank in all_player_data:
        player_stats[player_name]['total_score'] += score
        player_stats[player_name]['game_count'] += 1
        player_stats[player_name]['rank_sum'] += rank

    team_totals = defaultdict(float)
    for team, members in draft_teams.items():
        for member in members:
            team_totals[team] += player_stats[member]['total_score']

    sorted_teams = sorted(team_totals.items(), key=lambda x: x[1], reverse=True)
    
    # --- 2. 時系列データの作成 (グラフ用) ---
    # 試合ごとにグループ化
    games_map = defaultdict(list)
    for game_title, player_name, score, rank in all_player_data:
        games_map[game_title].append({'name': player_name, 'score': score})
    
    # 時系列変数の初期化
    history_dates = ['開幕前']
    team_history = {team: [0.0] for team in draft_teams.keys()}
    current_team_scores = {team: 0.0 for team in draft_teams.keys()}
    
    # 試合順に処理 (games_mapは挿入順＝時系列順と仮定)
    for game_title, players in games_map.items():
        history_dates.append(game_title.split(' ')[0]) # 日付部分だけ簡易抽出
        
        # この試合での変動を計算
        for p in players:
            # どのチームの選手か探す
            for team, members in draft_teams.items():
                if p['name'] in members:
                    current_team_scores[team] += p['score']
                    break
        
        # 履歴に追加
        for team in draft_teams.keys():
            team_history[team].append(round(current_team_scores[team], 1))

    # --- 3. サンプルチーム用データ (全選手リスト) ---
    all_players_info = []
    # すでに集計した player_stats から作成
    for player_name, stats in player_stats.items():
        all_players_info.append({
            'name': player_name,
            'score': round(stats['total_score'], 1)
        })
    # スコア順にソート (選びやすくするため)
    all_players_info.sort(key=lambda x: x['score'], reverse=True)


    # --- 4. HTML生成 ---
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
        .team-members {{ margin-top: 15px; font-size: 0.9rem; color: var(--text-sub); border-top: 1px solid #333; padding-top: 10px; }}

        /* グラフエリア */
        .chart-container {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            height: 400px;
            position: relative;
        }}

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
        select {{
            width: 100%;
            padding: 10px;
            background-color: #333;
            color: white;
            border: 1px solid #555;
            border-radius: 6px;
            font-size: 1rem;
        }}
        .my-team-result {{
            text-align: center;
            border-top: 1px solid #444;
            padding-top: 20px;
        }}
        .my-total-label {{ font-size: 1.2rem; color: var(--text-sub); }}
        .my-total-score {{ font-size: 3rem; font-weight: bold; color: var(--accent); }}

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

        footer {{ text-align: center; margin-top: 40px; color: var(--text-sub); font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>M-League Dashboard</h1>
            <div class="timestamp">Last Updated: {now_str}</div>
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

        <!-- 2. スコア推移グラフ -->
        <section>
            <h2>Score History</h2>
            <div class="chart-container">
                <canvas id="historyChart"></canvas>
            </div>
        </section>

        <!-- 3. サンプルチーム作成 -->
        <section>
            <h2>Create Your Sample Team</h2>
            <div class="sample-team-container">
                <p style="color: #aaa; margin-bottom: 15px;">好きな選手を4人選んで、合計スコアを計算できます。</p>
                <div class="selectors-grid">
                    <select id="p1" onchange="calculateMyTeam()"><option value="0">Select Player 1</option></select>
                    <select id="p2" onchange="calculateMyTeam()"><option value="0">Select Player 2</option></select>
                    <select id="p3" onchange="calculateMyTeam()"><option value="0">Select Player 3</option></select>
                    <select id="p4" onchange="calculateMyTeam()"><option value="0">Select Player 4</option></select>
                </div>
                <div class="my-team-result">
                    <div class="my-total-label">Estimated Total Score</div>
                    <div class="my-total-score" id="myScore">0.0</div>
                </div>
            </div>
        </section>

        <!-- 4. 個人成績 -->
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
                            <th>Games</th>
                            <th>Avg Rank</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    player_data_list = []
    # チーム所属選手のみを対象 (configにあるチームのメンバー)
    valid_players = set()
    for players in draft_teams.values():
        valid_players.update(players)

    # グラフやサンプルチーム用に全選手が必要な場合もあるが、Rankingはドラフト選手メインで出す
    for player, stats in player_stats.items():
        if player not in valid_players:
            continue
            
        final_score = stats['total_score']
        avg_rank = stats['rank_sum'] / stats['game_count'] if stats['game_count'] > 0 else 0
        
        # 所属チーム
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
        // --- データ埋め込み ---
    """

    # JS用: グラフデータ
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

    # JS用: 選手データ (サンプルチーム用)
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

        // セレクトボックス初期化
        playerMap.forEach(p => {
            const optionText = `${p.name} (${p.score > 0 ? '+' : ''}${p.score})`;
            selects.forEach(sel => {
                const opt = document.createElement('option');
                opt.value = p.score;
                opt.textContent = optionText;
                sel.appendChild(opt);
            });
        });

        function calculateMyTeam() {
            let total = 0.0;
            selects.forEach(sel => {
                total += parseFloat(sel.value);
            });
            const display = document.getElementById('myScore');
            display.textContent = (total > 0 ? '+' : '') + total.toFixed(1);
            
            if (total >= 0) {
                display.style.color = '#4CAF50';
            } else {
                display.style.color = '#FF5252';
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
