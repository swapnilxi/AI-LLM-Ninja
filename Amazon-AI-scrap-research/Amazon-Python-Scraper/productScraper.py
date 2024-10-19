import os
import csv
from bs4 import BeautifulSoup

# Step 1: Specify the file name. Leave this empty to scrape all files in the default folder.
myFileName = ''  # Example: 'specifiedFile.html'

# Step 2: Fixed folder name for personal product files
specific_folder = 'ProductFiles/myProductFilesFolder'

# Directory for the default HTML files folder
default_directory = 'ProductFiles'

# CSV output file
output_file = 'amazonExtracted.csv'

# Step 3: Headers for the CSV
headers = ['File Name', 'Product Title', 'Description', 'Product Insights', 'Pricing', 'Table Data', 'Feature Bullets']

# Step 4: Function to extract the necessary data from each HTML file
def extract_product_info(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    soup = BeautifulSoup(content, 'lxml')

    # Extract product title
    title_tag = soup.find('span', class_='a-size-large product-title-word-break')
    title = title_tag.text.strip() if title_tag else 'N/A'

    # Extract description
    desc_tag = soup.find('div', id='productDescription')
    description = desc_tag.text.strip() if desc_tag else 'N/A'

    # Extract product insights
    insights_tag = soup.find('ul', class_='a-unordered-list a-vertical a-spacing-mini')
    insights = ', '.join([li.text.strip() for li in insights_tag.find_all('li')]) if insights_tag else 'N/A'

    # Extract pricing
    price_tag = soup.find('span', class_='a-price-whole')
    price = price_tag.text.strip() if price_tag else 'N/A'

    # Extract table data
    table_tag = soup.find('table', class_='a-keyvalue prodDetTable')
    table_data = ''
    if table_tag:
        rows = table_tag.find_all('tr')
        for row in rows:
            th = row.find('th').text.strip()
            td = row.find('td').text.strip()
            table_data += f"{th}: {td}, "

    # Extract feature bullets from 'featurebullets_feature_div'
    feature_bullets_tag = soup.find('div', id='featurebullets_feature_div')
    feature_bullets = ''
    if feature_bullets_tag:
        bullets = feature_bullets_tag.find_all('span', class_='a-list-item')
        feature_bullets = ', '.join([bullet.text.strip() for bullet in bullets])

    return [file_path, title, description, insights, price, table_data, feature_bullets]

# Step 5: Function to check for existing processed files in the CSV
def get_processed_files(csv_file):
    processed_files = set()
    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip the header
            for row in reader:
                processed_files.add(row[0])  # Add the 'File Name' column to the set
    return processed_files

# Step 6: Function to process either a specific file or all files in the directory
def process_files(specific_file=None):
    processed_files = get_processed_files(output_file)
    file_exists = os.path.exists(output_file)

    # Step 7: Open the CSV file in append mode and write headers if it's new
    with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        if not file_exists:
            writer.writerow(headers)  # Write the header row if the file is new

        # Step 8: If a specific file is given, process only that file
        if specific_file:
            if specific_file in processed_files:
                print(f"Skipping already processed file: {specific_file}")
            else:
                try:
                    product_info = extract_product_info(specific_file)
                    writer.writerow(product_info)
                    print(f"Extracted data from {specific_file}")
                except Exception as e:
                    print(f"Failed to extract data from {specific_file}: {e}")
        else:
            # Step 9: Loop through all files in the default 'ProductFiles' directory
            for filename in os.listdir(default_directory):
                if filename.endswith(".html"):  # Process only HTML files
                    file_path = os.path.join(default_directory, filename)

                    if file_path in processed_files:
                        print(f"Skipping already processed file: {filename}")
                        continue

                    try:
                        product_info = extract_product_info(file_path)
                        writer.writerow(product_info)
                        print(f"Extracted data from {filename}")
                    except Exception as e:
                        print(f"Failed to extract data from {filename}: {e}")

# Step 10: Main function to handle either default folder scraping or specific file extraction
if __name__ == "__main__":
    if myFileName:
        # Process the specific file from the fixed folder
        specific_file_path = os.path.join(specific_folder, myFileName)
        if os.path.exists(specific_file_path):
            process_files(specific_file_path)
        else:
            print(f"File not found: {specific_file_path}")
    else:
        # Scrape all files in the default folder if no file is specified
        process_files()
