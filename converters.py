import os
import json
import xml.etree.ElementTree as ET
from PIL import Image
from ir_label import ImageInfo, BBox


# =================== Importers(To IR) =================

class VOCImporter:
    def parse(self, xml_path: str) -> ImageInfo:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        filename = root.find('filename').text
        size_node = root.find('size')
        width = int(size_node.find('width').text)
        height = int(size_node.find('height').text)
        img_path = os.path.join(os.path.dirname(xml_path), filename)
        info = ImageInfo(filename=filename, img_path=img_path, width=width, height=height)
        for obj in root.findall('object'):
            label = obj.find('name').text
            bndbox = obj.find('bndbox')
            info.bboxes.append(BBox(
                label=label,
                xmin=float(bndbox.find('xmin').text),
                ymin=float(bndbox.find('ymin').text),
                xmax=float(bndbox.find('xmax').text),
                ymax=float(bndbox.find('ymax').text)
            ))
        return info


class YOLOImporter:
    def parse(self, txt_path: str, img_path: str, class_names: list) -> ImageInfo:
        with Image.open(img_path) as img:
            w, h = img.size
        filename = os.path.basename(img_path)
        info = ImageInfo(filename=filename, img_path=img_path, width=w, height=h)
        with open(txt_path, 'r') as f:
            lines = f.readlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5: continue
            cls_id = int(parts[0])
            cx, cy, nw, nh = map(float, parts[1:5])
            label = class_names[cls_id] if cls_id < len(class_names) else str(cls_id)
            xmin = (cx - nw / 2) * w
            ymin = (cy - nh / 2) * h
            xmax = (cx + nw / 2) * w
            ymax = (cy + nh / 2) * h
            info.bboxes.append(BBox(label, xmin, ymin, xmax, ymax))
        return info

class LabelMeImporter:
    def parse(self, json_path: str) -> ImageInfo:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # filename = data.get('imagePath', os.path.basename(json_path).replace('.json', '.jpg'))
        # filename = os.path.basename(json_path).replace('.json', '.jpg'))
        filename = None
        dir_path = os.path.dirname(json_path)
        for ext in ['.jpg', '.png', '.jpeg', '.bmp']:
            name_try = os.path.basename(json_path).replace('.json', ext)
            file_try = os.path.join(dir_path, name_try)
            if os.path.exists(file_try):
                filename = name_try
                break
        if filename is None:
             filename = os.path.basename(data.get('imagePath', ''))
        width = data.get('imageWidth')
        height = data.get('imageHeight')
        img_path = os.path.join(os.path.dirname(json_path), filename)
        info = ImageInfo(filename=filename, img_path=img_path, width=width, height=height)
        for shape in data.get('shapes', []):
            label = shape['label']
            points = shape['points']
            # NOTE: LabelMe 可能是多边形，取外接矩形
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            info.bboxes.append(BBox(
                label=label,
                xmin=min(xs), ymin=min(ys),
                xmax=max(xs), ymax=max(ys)
            ))
        return info


class COCOImporter:
    def parse_all(self, json_path: str, img_root_dir: str) -> list[ImageInfo]:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cats = {c['id']: c['name'] for c in data['categories']}
        imgs = {i['id']: i for i in data['images']}
        img_infos = {}
        for img_id, img_data in imgs.items():
            fname = img_data['file_name']
            img_infos[img_id] = ImageInfo(
                filename=fname,
                img_path=os.path.join(img_root_dir, fname),
                width=img_data['width'],
                height=img_data['height']
            )
        for ann in data['annotations']:
            img_id = ann['image_id']
            if img_id not in img_infos: continue
            cat_name = cats.get(ann['category_id'], 'unknown')
            x, y, w, h = ann['bbox']
            bbox = BBox(label=cat_name, xmin=x, ymin=y, xmax=x + w, ymax=y + h)
            img_infos[img_id].bboxes.append(bbox)
        return list(img_infos.values())


# ===================== Exporters(From IR)==================
class YOLOExporter:
    def export(self, info_list: list[ImageInfo], output_dir: str, class_list: list = None):
        os.makedirs(output_dir, exist_ok=True)
        if not class_list:
            all_labels = set()
            for info in info_list:
                for box in info.bboxes:
                    all_labels.add(box.label)
            class_list = sorted(list(all_labels))
            with open(os.path.join(output_dir, 'classes.txt'), 'w') as f:
                f.write('\n'.join(class_list))
                # f.write('\n'.join([str(i) + ': ' + name for i, name in enumerate(class_list)]))

        cls_map = {name: i for i, name in enumerate(class_list)}

        for info in info_list:
            txt_name = os.path.splitext(info.filename)[0] + ".txt"
            with open(os.path.join(output_dir, txt_name), 'w') as f:
                for box in info.bboxes:
                    if box.label not in cls_map: continue
                    cls_id = cls_map[box.label]
                    cx, cy, w, h = box.to_yolo(info.width, info.height)
                    f.write(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")


class VOCExporter:
    def export(self, info: ImageInfo, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)

        root = ET.Element("annotation")
        # folder
        folder_name = os.path.basename(os.path.dirname(info.img_path))
        if not folder_name:
            folder_name = "Unspecified"     # 防止空路径
        ET.SubElement(root, "folder").text = folder_name
        # Filename
        ET.SubElement(root, "filename").text = info.filename
        # Path
        ET.SubElement(root, "path").text = os.path.abspath(info.img_path)
        # source
        source = ET.SubElement(root, "source")
        ET.SubElement(source, "database").text = "Unknown"
        # Size
        size = ET.SubElement(root, "size")
        ET.SubElement(size, "width").text = str(info.width)
        ET.SubElement(size, "height").text = str(info.height)
        ET.SubElement(size, "depth").text = "3"     # NOTE: 默认为彩色图片
        # Segmented
        ET.SubElement(root, "segmented").text = "0"
        # Object
        for box in info.bboxes:
            obj = ET.SubElement(root, "object")
            ET.SubElement(obj, "name").text = box.label
            ET.SubElement(obj, "pose").text = "Unspecified" # 固定格式
            ET.SubElement(obj, "truncated").text = "0"      # 固定格式
            ET.SubElement(obj, "difficult").text = "0"      # 固定格式
            bndbox = ET.SubElement(obj, "bndbox")
            ET.SubElement(bndbox, "xmin").text = str(int(box.xmin))
            ET.SubElement(bndbox, "ymin").text = str(int(box.ymin))
            ET.SubElement(bndbox, "xmax").text = str(int(box.xmax))
            ET.SubElement(bndbox, "ymax").text = str(int(box.ymax))
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        xml_name = os.path.splitext(info.filename)[0] + ".xml"
        tree.write(os.path.join(output_dir, xml_name), encoding="utf-8", xml_declaration=False)


class COCOExporter:
    def export(self, info_list: list[ImageInfo], output_path: str):
        categories = set()
        for info in info_list:
            for box in info.bboxes:
                categories.add(box.label)
        cat_list = sorted(list(categories))
        cat_map = {name: i + 1 for i, name in enumerate(cat_list)}  # COCO id 通常从1开始

        coco_data = {
            "images": [],
            "annotations": [],
            "categories": [{"id": v, "name": k} for k, v in cat_map.items()]
        }

        ann_id_cnt = 1
        for img_id, info in enumerate(info_list, 1):
            coco_data["images"].append({
                "id": img_id,
                "file_name": info.filename,
                "width": info.width,
                "height": info.height
            })

            for box in info.bboxes:
                coco_data["annotations"].append({
                    "id": ann_id_cnt,
                    "image_id": img_id,
                    "category_id": cat_map[box.label],
                    "bbox": [box.xmin, box.ymin, box.get_width(), box.get_height()],
                    "area": box.get_width() * box.get_height(),
                    "iscrowd": 0
                })
                ann_id_cnt += 1

        with open(output_path, 'w') as f:
            json.dump(coco_data, f)



class LabelMeExporter:
    def export(self, info: ImageInfo, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        data = {
            "version": "5.5.0",
            "flags": {},
            "shapes": [],
            "imagePath": info.filename,
            "imageData": None,  # NOTE: 设为 None，LabelMe 打开时会自动读取同级目录下的图片
            "imageHeight": info.height,
            "imageWidth": info.width
        }

        for box in info.bboxes:
            shape = {
                "label": box.label,
                "points": [
                    [box.xmin, box.ymin],
                    [box.xmax, box.ymax]
                ],
                "group_id": None,
                "description": "",
                "shape_type": "rectangle",  # NOTE: 因为是目标检测，这个硬编码为矩形
                "flags": {},
                "mask": None
            }
            data["shapes"].append(shape)

        json_name = os.path.splitext(info.filename)[0] + ".json"
        save_path = os.path.join(output_dir, json_name)

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)