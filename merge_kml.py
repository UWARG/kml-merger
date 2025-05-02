import sys
import argparse
import math
from xml.etree import ElementTree as ET
import xml.dom.minidom
from geopy.distance import geodesic # type: ignore
from itertools import combinations

## CONSTANTS ##
DIST_THRESHOLD_METERS = 5.0 # Distance threshold for duplicates
OUTPUT_KML = "merged_output.kml" # Output KML file name
## CONSTANTS ##


# Utility function to calculate distance between two points using geodesic.
def distance(p1, p2):
    return geodesic((p1[0], p1[1]), (p2[0], p2[1])).meters


# Function to parse KML files and extract coordinates.
# It returns a list of tuples containing (latitude, longitude, placemark element, file name).
def parse_kml_file(filepath):
    tree = ET.parse(filepath)
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    points = []

    for placemark in tree.findall(".//kml:Placemark", ns):
        coord_elem = placemark.find(".//kml:coordinates", ns)
        if coord_elem is not None:
            coords = coord_elem.text.strip().split(",")
            if len(coords) >= 2:
                lon, lat = map(float, coords[:2])
                points.append((lat, lon, placemark, filepath))

    return points


# Function to resolve duplicates based on user input.
# It groups points that are within DIST_THRESHOLD_METERS of each other and asks the user how to handle them.
def resolve_duplicates(points):
    resolved = []
    used = set()

    for i, (lat1, lon1, pm1, file1) in enumerate(points):
        if i in used:
            continue
        dup_group = [(lat1, lon1, pm1, i, file1)]
        for j, (lat2, lon2, pm2, file2) in enumerate(points):
            if i != j and j not in used:
                if distance((lat1, lon1), (lat2, lon2)) <= DIST_THRESHOLD_METERS:
                    dup_group.append((lat2, lon2, pm2, j, file2))
                    used.add(j)

        if len(dup_group) > 1:
            print(f"\nDuplicate points detected within {DIST_THRESHOLD_METERS} meters:")
            for idx, (lat, lon, pm, _, fname) in enumerate(dup_group):
                name_elem = pm.find('.//kml:name', {'kml': 'http://www.opengis.net/kml/2.2'})
                name = name_elem.text if name_elem is not None else 'N/A'
                print(f"{idx + 1}: {lat}, {lon}, name={name}, file={fname}")

            print("Options:")
            print("  a) merge (average)")
            print("  b) pick specific points to keep")
            print("  c) take all")

            choice = input("Choose action (a/b/c): ").strip().lower()
            if choice == 'a':
                avg_lat = sum(p[0] for p in dup_group) / len(dup_group)
                avg_lon = sum(p[1] for p in dup_group) / len(dup_group)
                resolved.append((avg_lat, avg_lon))
            elif choice == 'b':
                indices = list(map(int, input("Enter indices to keep (space-separated): ").split()))
                for idx in indices:
                    lat, lon, *_ = dup_group[idx - 1]
                    resolved.append((lat, lon))
            else:
                for lat, lon, *_ in dup_group:
                    resolved.append((lat, lon))
        else:
            resolved.append((lat1, lon1))

        used.add(i)

    return resolved


# Function to get the source point from user input.
def get_source_point():
    print("\n--- Enter Source Point Information ---")
    source_name = "Source"
    source_description = input("Description: ").strip()
    source_lat = float(input("Latitude: ").strip())
    source_lon = float(input("Longitude: ").strip())
    return (source_name, source_description, source_lat, source_lon)


# Function to create a merged KML file with the source point and hotspots.
def create_merged_kml(points, source_point):
    kml_ns = 'http://www.opengis.net/kml/2.2'
    ET.register_namespace('', kml_ns)
    kml = ET.Element('{%s}kml' % kml_ns)
    doc = ET.SubElement(kml, 'Document')

    src_name, src_desc, src_lat, src_lon = source_point
    source_pm = ET.SubElement(doc, 'Placemark')
    name = ET.SubElement(source_pm, 'name')
    name.text = src_name
    desc = ET.SubElement(source_pm, 'description')
    desc.text = src_desc
    point = ET.SubElement(source_pm, 'Point')
    coords = ET.SubElement(point, 'coordinates')
    coords.text = f"{src_lon},{src_lat},0"

    for i, (lat, lon) in enumerate(points, start=1):
        placemark = ET.SubElement(doc, 'Placemark')
        name = ET.SubElement(placemark, 'name')
        name.text = f"Hotspot {i}"
        point = ET.SubElement(placemark, 'Point')
        coords = ET.SubElement(point, 'coordinates')
        coords.text = f"{lon},{lat},0"

    return ET.ElementTree(kml)


# Main function to handle command line arguments and process KML files.
def main():
    parser = argparse.ArgumentParser(description="Merge KML files and label hotspots.")
    parser.add_argument("files", metavar="KML", nargs='+', help="Input KML files")

    args = parser.parse_args()
    all_points = []
    
    source_point = get_source_point()

    for file in args.files:
        print(f"Parsing {file}...")
        all_points.extend(parse_kml_file(file))

    print(f"\nTotal points before duplicate resolution: {len(all_points)}")

    unique_points = resolve_duplicates(all_points)

    print(f"\nFinal number of points: {len(unique_points)}")
    
    merged_kml = create_merged_kml(unique_points, source_point)
    rough_string = ET.tostring(merged_kml.getroot(), encoding='utf-8')
    reparsed = xml.dom.minidom.parseString(rough_string)
    with open(OUTPUT_KML, "w", encoding='utf-8') as f:
        f.write(reparsed.toprettyxml(indent="  "))
        
    print(f"Merged KML written to {OUTPUT_KML}")

if __name__ == "__main__":
    main()
