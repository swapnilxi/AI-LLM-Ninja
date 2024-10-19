
# Amazon Scraper Project

This repository contains two Python scripts designed for scraping data from Amazon:

1. **`pageScraper.py`**: Scrapes product listings from search result pages (e.g., product listings).
2. **`productScraper.py`**: Extracts detailed product information from specific product pages.

Both scripts scrape relevant product information (title, rating, price, etc.) and store the data in CSV files.

## Project Structure

- `PageFiles/`: Folder containing HTML files for scraping Amazon search result pages.
- `ProductFiles/`: Folder containing HTML files for scraping individual Amazon product pages.
- `pageScraper.py`: Script to scrape Amazon product listings from HTML search result pages.
- `productScraper.py`: Script to scrape product details from Amazon product HTML files.
- `pageResults.csv`: CSV output for pageScraper.py results.
- `amazonExtracted.csv`: CSV output for productScraper.py results.
- `README.md`: Instructions and usage information.

## Prerequisites

To run the scripts, you need the following:

1. Python 3.x installed.
2. Required Python libraries:
   - `beautifulsoup4`
   - `lxml`

You can install the dependencies by running:

```
pip install beautifulsoup4 lxml
```

## Usage

### 1. **`pageScraper.py`**: Scrape Amazon Product Listings

This script scrapes product data (title, rating, price, link) from the HTML files stored in the `PageFiles` directory. It checks for duplicates based on the product link to avoid scraping the same products more than once.

#### Steps to Use:

1. **Store HTML Files**: Place the HTML files containing Amazon search result pages in the `PageFiles` folder.
2. **Run the script**:
   - By default, the script processes all HTML files in the `PageFiles` directory:
   
```
python pageScraper.py
```

3. **Optional**: You can specify a single file to scrape by setting the `MySpecifiedFile` variable inside the script:

```
MySpecifiedFile = "amazon1.html"
```

Then run:

```
python pageScraper.py
```

4. **Output**: The data will be saved in `pageResults.csv` with the following columns:
   - `title`
   - `rating`
   - `price`
   - `link`

#### Duplicate Check:

The script automatically checks the `pageResults.csv` for existing product links and skips scraping duplicate products.

### 2. **`productScraper.py`**: Scrape Amazon Product Details

This script extracts detailed product information (e.g., title, features, product overview) from individual product pages stored in the `ProductFiles` directory.

#### Steps to Use:

1. **Store HTML Files**: Place the Amazon product HTML files in the `ProductFiles` folder.
2. **Run the script**:
   - By default, the script processes all HTML files in the `ProductFiles` directory:

```
python productScraper.py
```

3. **Output**: The data will be saved in `amazonExtracted.csv`, which includes:
   - Product Title
   - Features
   - Product Overview
   - Product Details

## Folder Structure

- `PageFiles/`: Store the HTML files containing Amazon search result pages here for scraping with `pageScraper.py`.
- `ProductFiles/`: Store the individual Amazon product HTML files here for scraping with `productScraper.py`.

## Notes

These scripts are designed to work with static HTML files downloaded from Amazon pages. Ensure that the HTML files are stored in the correct folders (`PageFiles` for search result pages, `ProductFiles` for individual product pages) before running the scripts.

**Respect Terms of Use**: Always respect Amazon’s robots.txt and terms of service. These scripts are intended for educational purposes only.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

This version contains basic formatting, and you can further modify it to fit your style. Let me know if you need any more changes!