import json
from bs4 import BeautifulSoup

# Step 1: Read the index.html file
with open('amazon1.html', 'r', encoding='utf-8') as file:
    content = file.read()

# Step 2: Parse the file with BeautifulSoup
soup = BeautifulSoup(content, 'lxml')

# Step 3: Find all divs with the relevant class
items = soup.find_all('div', class_='sg-col-4-of-24 sg-col-4-of-12 s-result-item s-asin sg-col-4-of-16 sg-col s-widget-spacing-small sg-col-4-of-20')

# Step 4: Initialize an empty list to store data
data = []

# Step 5: Loop through each item and extract link, title, rating, and price
for item in items:
    try:
        # Extracting the product link
        link_tag = item.find('a', class_='a-link-normal')
        link = link_tag['href'] if link_tag else ''

        # Extracting the image source
        image_tag = item.find('img', class_='s-image')
        image_src = image_tag['src'] if image_tag else ''

        # Extracting the title
        title_tag = item.find('span', class_='a-size-base-plus a-color-base a-text-normal')
        title = title_tag.text if title_tag else ''

        # Extracting the rating
        rating_tag = item.find('span', class_='a-icon-alt')
        rating = rating_tag.text if rating_tag else ''

        # Extracting the price
        price_tag = item.find('span', class_='a-price-whole')
        price = price_tag.text if price_tag else ''

        # Step 6: Append the data to the list
        data.append({
            'link': link,
            'image_src': image_src,
            'title': title,
            'rating': rating,
            'price': price
        })
    except Exception as e:
        print(f"Error parsing an item: {e}")

# Step 7: Write the data to a JSON file
with open('data.json', 'w', encoding='utf-8') as json_file:
    json.dump(data, json_file, ensure_ascii=False, indent=4)

print("Data successfully written to data.json")
