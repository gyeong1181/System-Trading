import os
import zipfile
import pandas as pd
import glob

# 경로 설정
extract_folder = "D:/코딩/자동매매/EMA+RSI/binance_data"
output_file = "D:/코딩/자동매매/EMA+RSI/merged_btcusdt_1h.csv"

# 압축 해제
for file in os.listdir(extract_folder):
    if file.endswith(".zip"):
        filepath = os.path.join(extract_folder, file)
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        print(f"✅ 추출 완료: {file}")

# CSV 병합
csv_files = glob.glob(os.path.join(extract_folder, "*.csv"))
df_list = []

for f in sorted(csv_files):
    try:
        df = pd.read_csv(f, header=0)  # 헤더 포함된 파일 읽기
        df_list.append(df)
    except Exception as e:
        print(f"❌ 오류 발생: {f} | {e}")

# 병합 및 저장
if df_list:
    merged_df = pd.concat(df_list, ignore_index=True)
    print("✅ 병합 완료")
    
    # 날짜형 컬럼 변환 (필요시)
    if "open_time" in merged_df.columns:
        merged_df["date"] = pd.to_datetime(merged_df["open_time"], unit='ms')
    
    merged_df.to_csv(output_file, index=False)
    print(f"💾 저장 완료: {output_file}")
else:
    print("⚠️ 병합할 파일이 없습니다.")
