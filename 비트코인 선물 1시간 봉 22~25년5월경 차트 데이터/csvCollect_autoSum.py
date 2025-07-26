import os
import zipfile
import glob
import pandas as pd

# 경로 설정 (네 환경에 맞게 수정 가능)
zip_folder = "D:/코딩/자동매매/EMA+RSI/binance_data"
extract_folder = os.path.join(zip_folder, "extracted_csvs")
os.makedirs(extract_folder, exist_ok=True)

csv_paths = []

# 모든 zip 파일 탐색
zip_files = glob.glob(os.path.join(zip_folder, "*.zip"))
print(f"총 zip 파일 개수: {len(zip_files)}")

for zip_path in zip_files:
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            print(f"[{os.path.basename(zip_path)}] 안의 파일들: {members}")

            for member in members:
                if member.endswith(".csv"):
                    extract_path = os.path.join(extract_folder, os.path.basename(member))
                    with open(extract_path, 'wb') as out_file:
                        out_file.write(zip_ref.read(member))
                    csv_paths.append(extract_path)
    except Exception as e:
        print(f"❌ 오류 발생: {zip_path} → {e}")

print(f"\n실제로 추출된 CSV 개수: {len(csv_paths)}")

# CSV 병합
if csv_paths:
    df_list = [pd.read_csv(f, header=None) for f in sorted(csv_paths)]
    merged_df = pd.concat(df_list, ignore_index=True)

    # 컬럼 이름 지정
    merged_df.columns = [
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_base_vol",
        "taker_quote_vol", "ignore"
    ]
    merged_df["date"] = pd.to_datetime(merged_df["timestamp"], unit='ms')

    # 저장
    output_path = os.path.join(zip_folder, "merged_btcusdt_1h.csv")
    merged_df.to_csv(output_path, index=False)
    print(f"\n✅ 병합 완료! → {output_path}")

else:
    print("\n❗ 병합할 CSV 파일이 없습니다. 압축 구조를 다시 확인하세요.")
