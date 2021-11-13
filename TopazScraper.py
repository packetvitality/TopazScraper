from lxml import html
import requests
import xml.etree.ElementTree as ET
from time import sleep
from tqdm import tqdm
import os
import csv
import re
import json

class ProductScrape:
    def __init__(self, result_file, error_file):
        self.results_file = result_file
        self.error_file = error_file
        self.encoding = 'Windows-1252'

    def get_spider_urls(self, zap_output):
        """"
        Parses result file from OWASP ZAP spider.
        Appends results to the URL set to be used by other functions
        """
        urls = set()
        with open(zap_output, encoding=self.encoding) as file:
            for line in file:
                if "true" in line:
                    if "sorting" not in line.lower():
                        url_dirty = line.split(",")[2]
                        url_clean = url_dirty.split("?")[0]
                        urls.add(url_clean)
        return urls

    def get_sitemap_urls(self, sitemap):
        """
        Pulls a provided sitemap URL.
        Parses the result and adds URLs to the URL set to be used by other functions
        """

        urls = set()
        r = requests.get(sitemap)
        root = ET.fromstring(r.content)

        for child in root:
            url = child[4].attrib.get('href')
            urls.add(url)
        return urls

        ## Prob the better way to do it, but need to understand the XML better
        # for child in root.iter("link"):
        #     print(child.attrib)
        #     sleep(1)

    def get_sku(self, url,content):
        try:
            tree = html.fromstring(content)
            sku = tree.xpath('//span[@class="value"]/text()')[0]
            return sku
        except Exception as e:
            with open(self.error_file, 'a', encoding=self.encoding) as file:
                error = f"URL {url} failed to parse the SKU. {e}"
                file.write(error)
                file.write("\n")
            return None
            
    def get_title(self, url, content):
        try:
            tree = html.fromstring(content)
            title = tree.xpath('//h1[@class="font-product-title"]/text()')[0]
            return title
        except Exception as e:
            with open(self.error_file, 'a', encoding=self.encoding) as file:
                error = f"URL {url} failed to parse the TITLE. {e}"
                file.write(error)
                file.write("\n")
            return None

    def get_description(self, url, content):
        try:
            tree = html.fromstring(content)
            description = tree.xpath('//*[@id="productPage"]/div[1]/div/div[2]/div[2]/div[2]/p/text()')[0]
            return description
        except:
            try:
                description = tree.xpath('//*[@id="productPage"]/div[1]/div/div[2]/div[2]/div[2]/text()')[0]
                return description
            except Exception as e:
                with open(self.error_file, 'a', encoding=self.encoding) as file:
                    error = f"URL {url} failed to parse the DESCRIPTION.{e}"
                    file.write(error)
                    file.write("\n")
                return None
    
    def get_upc(self, url, content):
        # UPC
        try:
            tree = html.fromstring(content)
            td_list = tree.xpath('//td[@class="value"]/text()')
            # The location of the UPC can move, so we search all of the results and look for a 12 digit value.
            for i in td_list:
                match = re.search(r"\d{12}", i)
                if match:
                    upc = i
                    break
            return upc
        except Exception as e:
            with open(self.error_file, 'a', encoding=self.encoding) as file:
                error = f"URL {url} failed to parse the UPC. {e}"
                file.write(error)
                file.write("\n")
            return None

    def get_image(self, url, content):
        # Tries to grab the largest product image available.
        try:
            base_url = "/".join(url.split("/")[0:3]) # Storing base url like https://site.com
            image_path = None
            tree = html.fromstring(content)
            site_images = tree.xpath('//img')
            for image in site_images:
                image_name = base_url + image.attrib.get('src').lower()
                if "product" in image_name and "large" in image_name:
                    if "large" in image_name:
                        image_path = image_name
                        break
            
            if not image_path:
                for image in site_images:
                    if "product" in image_name and "medium" in image_name:
                        image_path = image_name
                        break
            
            if not image_path:
                for image in site_images:
                    if "product" in image_name and "small" in image_name:
                        image_path = image_name
                        break
            return image_path

        except Exception as e:
            with open(self.error_file, 'a', encoding=self.encoding) as file:
                error = f"URL {url} failed to parse the Image Path(s). {e}"
                file.write(error)
                file.write("\n")
            return None

    def get_page_info(self, urls):
        """
        Requests content from URL's and isolates various product information on the page.
        Product information is written to a CSV file.
        """

        # Create Column Names for Result File
        with open(self.results_file, 'w', newline='', encoding=self.encoding) as file:
            fields = ['URL', 'SKU', 'TITLE', 'DESCRIPTION', 'UPC', 'IMAGE_PATH(s)'] 
            writer = csv.writer(file)
            writer.writerow(fields)
        
        for url in tqdm(urls, desc="Parsing Product Data from URLs"):
            try:
                r = requests.get(url)
                
                # Isolated page info
                sku = self.get_sku(url, r.content)
                title = self.get_title(url, r.content)
                description = self.get_description(url, r.content)
                upc = self.get_upc(url, r.content)
                image_path = self.get_image(url, r.content)

                # Write parsed date to results file
                result = [url, sku, title, description, upc, image_path]
                with open(self.results_file, 'a', newline='', encoding=self.encoding) as file:
                    writer = csv.writer(file)
                    writer.writerow(result)

            except Exception as e:
                with open(self.error_file, 'a', encoding=self.encoding) as file:
                    error = f"URL {url} failed, no additional processing. {e}"
                    file.write(error)
                    file.write("\n")
                result = [url, "FAILURE - SEE LOGS"]
                with open(self.results_file, 'a', newline='', encoding=self.encoding) as file:
                    writer = csv.writer(file)
                    writer.writerow(result)

def main():
    config_file = "config.json"
    with open(config_file) as file:
        config = json.load(file)
        for key, value in config.items():
            if key == "sitemap":
                sitemap = value
            if key == "zap_output":
                zap_output = value
            if key == "result_file":
                result_file = value
            if key == "error_file":
                error_file = value

    ps = ProductScrape(result_file, error_file)

    # Pull URL's via sitemap
    urls = ps.get_sitemap_urls(sitemap) 

    # Pull URL's from OWASP ZAP Spider Output File
    # urls = ps.get_spider_urls(zap_output)

    ps.get_page_info(urls)

if __name__ == "__main__":
    main()
