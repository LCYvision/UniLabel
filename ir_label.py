from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class BBox:
    label: str   # 类别名称 (统一用字符串，避免ID混乱)
    xmin: float  # 绝对坐标
    ymin: float
    xmax: float
    ymax: float

    def get_width(self): return self.xmax - self.xmin

    def get_height(self): return self.ymax - self.ymin

    # 辅助：转为 YOLO 归一化格式
    def to_yolo(self, img_w, img_h):
        # 归一化后的中心点坐标
        cx = (self.xmin + self.xmax) / 2.0 / img_w
        cy = (self.ymin + self.ymax) / 2.0 / img_h
        # 归一化后的边界框宽高（不是图像的宽高）
        w = self.get_width() / img_w
        h = self.get_height() / img_h
        return cx, cy, w, h

@dataclass
class ImageInfo:
    filename: str   # 图片文件名 (e.g., "123.jpg")
    img_path: str   # 图片完整路径 (用于读取宽高或复制图片)
    width: int      # 图片真实宽
    height: int     # 图片真实高
    bboxes: List[BBox] = field(default_factory=list)
