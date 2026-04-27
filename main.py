import requests, json, webbrowser, os
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from datetime import datetime, timedelta

# [환경 설정]
# 직접 번호를 적지 않고, GitHub 금고(Secrets)에서 꺼내오도록 설정했습니다.
MOLIT_API_KEY = os.environ.get("7b6efd99b84e03fca06677a5f9632db682bac3e47d90f5ec37f3b4947e84307e")
SUPABASE_URL = os.environ.get("https://ofbtvvzpvuezfdirwhtd.supabase.co")
SUPABASE_KEY = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9mYnR2dnpwdnVlemZkaXJ3aHRkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwMjY1MTYsImV4cCI6MjA5MjYwMjUxNn0.OLCpaSiQxs37dZC3P0QXxOTp4OKRYYApaF34b2UkOlA")


HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json", 
    "Prefer": "resolution=merge-duplicates"
}

LOC_CODES = {'강남구': '11680', '서초구': '11650', '송파구': '11710', '분당구': '41135', '과천시': '41131', '광명시': '41210'}

def get_max_price(apt_name):
    url = f"{SUPABASE_URL}/rest/v1/seoul_master?apt_id=ilike.*{apt_name}*&select=max_price"
    try:
        res = requests.get(url, headers=HEADERS).json()
        return res[0]['max_price'] if res else None
    except: return None

def fetch_data(months_to_fetch=3):
    if months_to_fetch == 0:
        create_html(); return

    print(f"📡 시그널 수집 중... (이 작업은 다소 시간이 걸릴 수 있습니다)")
    months = [(datetime.now() - timedelta(days=i*30)).strftime('%Y%m') for i in range(months_to_fetch)]
    
    for loc, code in LOC_CODES.items():
        for m in months:
            url = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
            params = {'serviceKey': unquote(MOLIT_API_KEY), 'LAWD_CD': code, 'DEAL_YMD': m}
            try:
                res = requests.get(url, params=params)
                items = ET.fromstring(res.text).findall('.//item')
                for i in items:
                    name = i.findtext('aptNm').strip()
                    price = int(i.findtext('dealAmount').replace(',', ''))
                    max_p = get_max_price(name)
                    if not max_p: continue
                    
                    diff = price - max_p
                    date = f"{i.findtext('dealYear')}-{i.findtext('dealMonth').zfill(2)}-{i.findtext('dealDay').zfill(2)}"
                    
                    if abs(diff) >= 5000:
                        payload = {"loc_name": loc, "apt_name": name, "current_price": price, "drop_amount": diff, "deal_date": date}
                        requests.post(f"{SUPABASE_URL}/rest/v1/drop_results", headers=HEADERS, data=json.dumps(payload))
            except: continue
    create_html()

def create_html():
    html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>부동산 폭등 폭락 시그널 추적기</title>
        <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
        <style>
            :root {{ --blue: #3b82f6; --red: #ef4444; --dark: #0f172a; --gray: #f8fafc; }}
            body {{ font-family: 'Pretendard', -apple-system, sans-serif; background: var(--gray); margin: 0; padding: 20px; color: var(--dark); }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            .download-group {{ display: flex; gap: 10px; }}
            .btn-download {{ background: #10b981; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.9rem; transition: 0.2s; }}
            .btn-download:hover {{ background: #059669; }}

            .filter-panel {{ background: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; gap: 40px; }}
            .btn-group button {{ background: #f1f5f9; border: none; padding: 10px 18px; border-radius: 12px; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: 0.2s; }}
            .btn-group button.active {{ background: var(--dark); color: white; }}

            .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .chart-card {{ background: white; padding: 25px; border-radius: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); position: relative; }}
            .chart-card h3 {{ margin-top: 0; display: flex; justify-content: space-between; align-items: center; }}
            .reset-loc {{ font-size: 0.7rem; color: var(--blue); cursor: pointer; border: 1px solid var(--blue); padding: 2px 8px; border-radius: 4px; display: none; }}

            .list-panel {{ background: white; padding: 30px; border-radius: 28px; box-shadow: 0 10px 40px rgba(0,0,0,0.03); }}
            .tabs {{ display: flex; gap: 20px; margin-bottom: 25px; border-bottom: 2px solid #f1f5f9; }}
            .tab-btn {{ font-size: 1.4rem; border: none; background: none; cursor: pointer; color: #cbd5e1; font-weight: 800; padding-bottom: 15px; }}
            .tab-btn.active.down {{ color: var(--blue); border-bottom: 4px solid var(--blue); }}
            .tab-btn.active.up {{ color: var(--red); border-bottom: 4px solid var(--red); }}
            
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ text-align: left; padding: 15px; color: #94a3b8; font-size: 0.85rem; }}
            td {{ padding: 20px 15px; border-bottom: 1px solid #f8fafc; }}
            .price-tag {{ font-weight: 800; font-size: 1.1rem; }}
            .drop {{ color: var(--blue); }}
            .rise {{ color: var(--red); }}
            .btn-map {{ background: #fee500; border: none; padding: 8px 15px; border-radius: 10px; font-weight: bold; cursor: pointer; }}
            .filter-info {{ background: #e0f2fe; color: #0369a1; padding: 10px 20px; border-radius: 10px; margin-bottom: 15px; display: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="font-size: 1.8rem; letter-spacing: -1px;">📡 부동산 폭등 폭락 시그널 <span style="color:#64748b; font-weight:400;">양극단 추적기</span></h1>
                <div class="download-group">
                    <button class="btn-download" onclick="downloadExcel()">📊 Excel 시트 저장</button>
                </div>
            </div>

            <div class="filter-panel">
                <div class="filter-group"><label style="display:block; font-size:0.8rem; font-weight:bold; color:#64748b; margin-bottom:10px;">📅 거래 기간</label>
                    <div class="btn-group">
                        <button class="active" onclick="setFilter('period', 0, this)">전체</button>
                        <button onclick="setFilter('period', 6, this)">6개월</button>
                        <button onclick="setFilter('period', 12, this)">1년</button>
                        <button onclick="setFilter('period', 24, this)">2년</button>
                    </div>
                </div>
                <div class="filter-group"><label style="display:block; font-size:0.8rem; font-weight:bold; color:#64748b; margin-bottom:10px;">💰 변동 금액</label>
                    <div class="btn-group">
                        <button class="active" onclick="setFilter('price', 0, this)">전체</button>
                        <button onclick="setFilter('price', 10000, this)">1억↑</button>
                        <button onclick="setFilter('price', 30000, this)">3억↑</button>
                        <button onclick="setFilter('price', 50000, this)">5억↑</button>
                    </div>
                </div>
            </div>

            <div class="chart-grid">
                <div class="chart-card"><h3>📈 시장 심리</h3><canvas id="ratioChart"></canvas></div>
                <div class="chart-card">
                    <h3>📍 지역별 빈도 <span id="resetLoc" class="reset-loc" onclick="resetLocFilter()">해제</span></h3>
                    <p style="font-size:0.7rem; color:#94a3b8; margin-top:-10px;">*막대를 클릭하면 해당 지역만 필터링됩니다.</p>
                    <canvas id="locChart"></canvas>
                </div>
                <div class="chart-card"><h3>🏆 변동 TOP 5</h3><canvas id="topChart"></canvas></div>
            </div>

            <div class="list-panel">
                <div id="filter-status" class="filter-info"></div>
                <div class="tabs">
                    <button class="tab-btn active down" onclick="setMode('down', this)">📉 하락 시그널</button>
                    <button class="tab-btn up" onclick="setMode('up', this)">🔥 상승 시그널</button>
                </div>
                <table id="main-table">
                    <thead><tr><th>계약일</th><th>지역/단지명</th><th>실거래가</th><th>변동액</th><th>액션</th></tr></thead>
                    <tbody id="list"></tbody>
                </table>
            </div>
        </div>

        <script>
            const client = supabase.createClient("{SUPABASE_URL}", "{SUPABASE_KEY}");
            let rawData = []; let currentMode = 'down'; let filters = {{ period: 0, price: 0, loc: null }}; let charts = {{}};

            async function init() {{
                const {{ data }} = await client.from('drop_results').select('*').order('deal_date', {{ascending: false}});
                rawData = data; render();
            }}

            function setFilter(type, val, btn) {{
                filters[type] = val;
                btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active'); render();
            }}

            function setMode(m, btn) {{
                currentMode = m;
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active'); render();
            }}

            function resetLocFilter() {{
                filters.loc = null;
                document.getElementById('resetLoc').style.display = 'none';
                render();
            }}

            function getFilteredData() {{
                let filtered = rawData.filter(i => currentMode === 'up' ? i.drop_amount > 0 : i.drop_amount < 0);
                
                if(filters.loc) {{
                    filtered = filtered.filter(i => i.loc_name === filters.loc);
                }}
                if(filters.period > 0) {{
                    const cutoff = new Date(); cutoff.setMonth(cutoff.getMonth() - filters.period);
                    filtered = filtered.filter(i => new Date(i.deal_date) >= cutoff);
                }}
                if(filters.price > 0) {{
                    filtered = filtered.filter(i => Math.abs(i.drop_amount) >= filters.price);
                }}
                return filtered.sort((a,b) => currentMode === 'up' ? b.drop_amount - a.drop_amount : a.drop_amount - b.drop_amount);
            }}

            function render() {{
                const data = getFilteredData();
                updateCharts(data);

                // 지역 필터 상태 표시
                const status = document.getElementById('filter-status');
                if(filters.loc) {{
                    status.style.display = 'block';
                    status.innerText = `📍 ${{filters.loc}} 시그널만 표시 중`;
                }} else {{
                    status.style.display = 'none';
                }}

                document.getElementById('list').innerHTML = data.map(i => `
                    <tr>
                        <td style="color:#94a3b8; font-size:0.85rem;">${{i.deal_date}}</td>
                        <td>
                            <div style="font-size:0.75rem; color:#64748b;">${{i.loc_name}}</div>
                            <div style="font-weight:bold; font-size:1rem; cursor:pointer;" onclick="window.open('https://search.naver.com/search.naver?query=${{i.loc_name}} ${{i.apt_name}}', '_blank')">${{i.apt_name}}</div>
                        </td>
                        <td class="price-tag">${{(i.current_price/10000).toFixed(1)}}억</td>
                        <td class="price-tag ${{currentMode === 'up' ? 'rise' : 'drop'}}">
                            ${{currentMode === 'up' ? '▲' : '▼'}} ${{ (Math.abs(i.drop_amount)/10000).toFixed(1) }}억
                        </td>
                        <td><button class="btn-map" onclick="window.open('https://map.kakao.com/?q=${{i.loc_name}} ${{i.apt_name}}', '_blank')">MAP</button></td>
                    </tr>
                `).join('');
            }}

            function downloadExcel() {{
                const data = getFilteredData().map(i => ({{
                    "계약일": i.deal_date,
                    "지역": i.loc_name,
                    "단지명": i.apt_name,
                    "실거래가(억)": (i.current_price/10000).toFixed(2),
                    "변동액(억)": (i.drop_amount/10000).toFixed(2)
                }}));
                const worksheet = XLSX.utils.json_to_sheet(data);
                const workbook = XLSX.utils.book_new();
                XLSX.utils.book_append_sheet(workbook, worksheet, "시그널_리스트");
                XLSX.writeFile(workbook, `부동산_시그널_${{currentMode}}_${{new Date().toISOString().slice(0,10)}}.xlsx`);
            }}

            function updateCharts(data) {{
                // 1. 시장 심리 차트
                const ups = rawData.filter(i => i.drop_amount > 0).length;
                const downs = rawData.filter(i => i.drop_amount < 0).length;
                if(charts.ratio) charts.ratio.destroy();
                charts.ratio = new Chart(document.getElementById('ratioChart'), {{
                    type: 'doughnut', data: {{ labels: ['상승', '하락'], datasets: [{{ data: [ups, downs], backgroundColor: ['#ef4444', '#3b82f6'], borderWidth:0 }}] }},
                    options: {{ cutout: '75%' }}
                }});

                // 2. 지역별 빈도 차트 (클릭 이벤트 추가)
                const locCounts = {{}}; 
                // 차트에는 전체 데이터의 빈도를 보여주되, 클릭 시 필터링함
                const displayData = rawData.filter(i => currentMode === 'up' ? i.drop_amount > 0 : i.drop_amount < 0);
                displayData.forEach(i => locCounts[i.loc_name] = (locCounts[i.loc_name] || 0) + 1);
                
                if(charts.loc) charts.loc.destroy();
                charts.loc = new Chart(document.getElementById('locChart'), {{
                    type: 'bar', 
                    data: {{ 
                        labels: Object.keys(locCounts), 
                        datasets: [{{ label: '시그널 건수', data: Object.values(locCounts), backgroundColor: '#1e293b', borderRadius:8 }}] 
                    }},
                    options: {{
                        onClick: (e, elements) => {{
                            if (elements.length > 0) {{
                                const index = elements[0].index;
                                filters.loc = Object.keys(locCounts)[index];
                                document.getElementById('resetLoc').style.display = 'inline-block';
                                render();
                            }}
                        }},
                        plugins: {{ legend: {{ display: false }} }}
                    }}
                }});

                // 3. TOP 5 차트
                const sorted = [...data].sort((a,b) => Math.abs(b.drop_amount) - Math.abs(a.drop_amount)).slice(0, 5);
                if(charts.top) charts.top.destroy();
                charts.top = new Chart(document.getElementById('topChart'), {{
                    type: 'bar', options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }} }},
                    data: {{ labels: sorted.map(i => i.apt_name.substring(0,6)), datasets: [{{ label: '억', data: sorted.map(i => Math.abs(i.drop_amount)/10000), backgroundColor: '#64748b' }}] }}
                }});
            }}
            init();
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    webbrowser.open('file://' + os.path.realpath("index.html"))

if __name__ == "__main__":
    choice = input("1.업데이트  2.UI확인 : ")
    fetch_data(3 if choice == "1" else 0)
