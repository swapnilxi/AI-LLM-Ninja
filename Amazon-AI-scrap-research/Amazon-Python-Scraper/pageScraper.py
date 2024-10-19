import os
import csv
from bs4 import BeautifulSoup

# Variable to specify the file, if needed
MySpecifiedFile = ""  # Set this to the filename you want to process, e.g., 'amazon1.html'

# Step 1: Read the input HTML file
def read_html_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

# Step 2: Parse the file with BeautifulSoup
def parse_html(content):
    soup = BeautifulSoup(content, 'lxml')

    # Find all divs with the relevant class
    items = soup.find_all('div', class_='sg-col-4-of-24 sg-col-4-of-12 s-result-item s-asin sg-col-4-of-16 sg-col s-widget-spacing-small sg-col-4-of-20')

    # Step 3: Initialize an empty list to store data
    data = []

    # Step 4: Loop through each item and extract title, rating, price, and link
    for item in items:
        try:
            # Extracting the title
            title_tag = item.find('span', class_='a-size-base-plus a-color-base a-text-normal')
            title = title_tag.text if title_tag else ''

            # Extracting the rating
            rating_tag = item.find('span', class_='a-icon-alt')
            rating = rating_tag.text if rating_tag else ''

            # Extracting the price
            price_tag = item.find('span', class_='a-price-whole')
            price = price_tag.text if price_tag else ''

            # Extracting the product link
            link_tag = item.find('a', class_='a-link-normal')
            link = link_tag['href'] if link_tag else ''

            # Append the extracted data to the list
            data.append({
                'title': title,
                'rating': rating,
                'price': price,
                'link': link  # Link is now the last field
            })
        except Exception as e:
            print(f"Error parsing an item: {e}")
    
    return data

# Step 5: Check for duplicates
def read_existing_links(csv_filename):
    existing_links = set()
    if os.path.isfile(csv_filename):
        with open(csv_filename, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if 'link' in row and row['link']:
                    existing_links.add(row['link'])
    return existing_links

# Step 6: Write data to CSV, ensuring headers are written and checking for duplicates
def write_to_csv(data, csv_filename):
    # Read existing links to avoid duplicates
    existing_links = read_existing_links(csv_filename)

    # Filter out already scraped items based on links
    data = [item for item in data if item['link'] not in existing_links]

    if not data:  # If no new data to add, return
        print(f"No new data to add from the current file.")
        return

    # Check if file exists to determine whether to write headers
    file_exists = os.path.isfile(csv_filename)

    try:
        with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
            # The column order is set as: title, rating, price, link
            writer = csv.DictWriter(csvfile, fieldnames=['title', 'rating', 'price', 'link'])
            
            # If file doesn't exist, write the header
            if not file_exists:
                writer.writeheader()

            # Add a divider (an empty row) before appending new data
            writer.writerow({})

            # Write the rows
            writer.writerows(data)
    except Exception as e:
        print(f"Error writing to CSV: {e}")

# Main function to scrape the page and append to the CSV
def scrape_page(html_file, csv_filename='pageResults.csv'):
    # Read the HTML content
    content = read_html_file(html_file)
    
    # Parse the content and extract data
    data = parse_html(content)

    # Write or append data to the CSV file, checking for duplicates
    write_to_csv(data, csv_filename)
    
    print(f"Data from {html_file} successfully appended to {csv_filename}")

# Function to process all files in the 'PageFiles' folder
def process_all_files_in_folder(folder_path, csv_filename='pageResults.csv'):
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and file_name.endswith('.html'):
            scrape_page(file_path, csv_filename)

# Auto-run when script is executed
if __name__ == "__main__":
    base_folder = 'PageFiles'
    specific_folder = 'PageFiles/myPageFilesFolder'

    if MySpecifiedFile:
        # If a specific file is provided via the MySpecifiedFile variable, process only that file
        file_path = os.path.join(specific_folder, MySpecifiedFile)
        if os.path.isfile(file_path):
            scrape_page(file_path)
        else:
            print(f"Specified file {MySpecifiedFile} not found in {specific_folder}")
    else:
        # Process all files in the 'PageFiles' folder if MySpecifiedFile is empty
        process_all_files_in_folder(base_folder)
