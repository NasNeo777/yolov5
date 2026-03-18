import cv2
import numpy as np
import torch

from game_alone.NasGameConfig import NasGameConfig
from models.common import DetectMultiBackend
from utils.general import non_max_suppression, Profile
from utils.torch_utils import select_device


class YoloHead:
    def __init__(self, model_path, img_size, config):
        """
        初始化 YoloHead 模型
        :param model_path: YOLO 模型的权重路径
        """
        self.model_path = model_path
        self.config = config
        self.img_size = img_size
        self.device = select_device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = DetectMultiBackend(self.model_path, device=self.device, dnn=False,
                                        data=self.config.data,
                                        fp16=False)
        self.model.eval()
        self.names = self.model.names

        self.model.warmup(imgsz=(1, 3, self.img_size[0], self.img_size[1]))  # 预热模型

    def preprocess(self, frame):
        """
        预处理图像，将其转换为模型输入格式
        :param frame: 输入的单帧图像 (H, W, C)
        :return: 预处理后的图像张量
        """
        frame_resized, r, (dw, dh) = self.letterbox(frame, new_shape=self.img_size)  # 使用 letterbox 调整图像
        image = frame_resized.astype(np.float32) / 255.0  # 归一化
        image = np.transpose(image, (2, 0, 1))  # HWC -> CHW
        image = np.expand_dims(image, axis=0)  # 增加 batch 维度
        return torch.from_numpy(image).to(self.device), r, (dw, dh)

    def call(self, frame):
        """
        运行 YOLO 模型并返回处理后的帧
        :param frame: 输入的单帧图像
        :return: 带有检测框的帧
        """
        self.shape = frame.shape[:2]
        image, r, (dw, dh) = self.preprocess(frame)

        with Profile(device=self.device):
            pred = self.model(image, augment=False, visualize=False)

        return self.deal(pred, frame, r, (dw, dh))

    def deal(self, pred, frame, r, padding):
        """
        处理 YOLO 模型的预测结果，并在图像上绘制边界框
        :param pred: 模型的原始预测结果
        :param frame: 原始输入帧
        :param r: 缩放比例
        :param padding: 填充 (dw, dh)
        :return: 带有检测框和标签的帧
        """
        pred = non_max_suppression(pred, conf_thres=0.5, iou_thres=0.45, classes=None, agnostic=False, max_det=100)
        det = pred[0]
        x, y = 0.0, 0.0
        if det is not None and len(det):
            det[:, :4] -= torch.tensor(padding * 2, device=det.device)  # 去掉填充偏移
            det[:, :4] /= r  # 缩放回原始尺寸
            det[:, :4] = det[:, :4].round()  # 将框的坐标转换为整数

            # 选择离屏幕中心最近的目标（而非置信度最高）
            screen_cx = self.shape[1] / 2
            screen_cy = self.shape[0] / 2
            best_dist = float('inf')

            for *xyxy, conf, cls in reversed(det):
                x1, y1, x2, y2 = map(int, xyxy)
                confidence = float(conf)
                class_id = int(cls)

                # 打印调试信息
                print(f"Class: {self.names[class_id]}, Confidence: {confidence:.2f}, Coordinates: {x1, y1, x2, y2}")

                # 瞄准头部：取 box 顶部 + 15% 的高度处
                box_h = y2 - y1
                aim_x = (x1 + x2) / 2
                aim_y = y1 + box_h * 0.15

                # 到屏幕中心的距离
                dist = ((aim_x - screen_cx) ** 2 + (aim_y - screen_cy) ** 2) ** 0.5

                label = f"{self.names[class_id]} {confidence:.2f}"
                color = (0, 255, 0)  # 绿色
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # 绘制人头区域的红框
                box_w = x2 - x1
                # 假设头部宽度是身体宽度的 40%，高度是总高度的 25%
                head_w = int(box_w * 0.4)
                head_h = int(box_h * 0.25)
                head_x1 = int(aim_x - head_w / 2)
                head_y1 = int(y1)
                head_x2 = int(aim_x + head_w / 2)
                head_y2 = int(y1 + head_h)
                
                cv2.rectangle(frame, (head_x1, head_y1), (head_x2, head_y2), (0, 0, 255), 2)  # 红色人头框

                # 绘制标签
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                text_origin = (x1, y1 - 10 if y1 - 10 > 10 else y1 + 10)
                cv2.rectangle(frame, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), color, -1)
                cv2.putText(frame, label, text_origin, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # 选最近目标
                if dist < best_dist:
                    best_dist = dist
                    # 偏移量 = 瞄准点 - 屏幕中心
                    x = aim_x - screen_cx
                    y = aim_y - screen_cy
                    best_head_rect = (head_x1, head_y1, head_x2, head_y2)
        else:
            return {
                "frame": frame,
                "shoot": False,
                "x": x,
                "y": y
            }
        loc = (x + self.shape[1] / 2, y + self.shape[0] / 2)
        cv2.putText(frame, "0", tuple(map(int, loc)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        return {
            "frame": frame,
            "shoot": True,
            "x": x,
            "y": y,
            "head_rect": best_head_rect if 'best_head_rect' in locals() else None
        }

    def letterbox(self, image, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True):
        """
        将图像调整到目标大小，同时保持宽高比。
        :param image: 输入图像
        :param new_shape: 目标尺寸 (height, width)
        :param color: 填充颜色
        :param auto: 自动调整为最小尺寸
        :param scaleFill: 强制填充到目标大小
        :param scaleup: 是否允许放大图像
        :return: 调整后的图像和调整参数
        """
        shape = image.shape[:2]  # 当前图像的高度和宽度
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])  # 缩放比例
        if not scaleup:  # 仅缩小，不放大
            r = min(r, 1.0)

        new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))  # 调整后的尺寸
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # 填充
        if auto:  # 最小矩形
            dw, dh = np.mod(dw, 32), np.mod(dh, 32)  # 使填充量为32的倍数
        elif scaleFill:  # 强制填充
            dw, dh = 0, 0
            new_unpad = new_shape
            r = new_shape[1] / shape[1], new_shape[0] / shape[0]

        dw //= 2  # 左右填充
        dh //= 2  # 上下填充

        if shape[::-1] != new_unpad:  # 调整图像大小
            image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = dh, dh
        left, right = dw, dw
        image = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # 添加填充
        return image, r, (dw, dh)


if __name__ == '__main__':
    config = NasGameConfig()
    model = YoloHead(r'C:\Users\12700\PycharmProjects\yolov5\runs\train\exp7\weights\last.pt', (640, 640), config)
    frame = cv2.imread(
        r"C:\Users\12700\PycharmProjects\yolov5\mask\valid\images\r1400018548960op29s_jpg.rf.1aa9ecf11eb6e101f0bbdf0c3048702c.jpg")
    if frame is None:
        print("Error: Unable to read the input image.")
        exit(1)
    frame_with_detections = model.call(frame)
    if not frame_with_detections["shoot"]:
        print("Error: Unable to detect the input image.")
        exit(1)
    print(frame_with_detections["x"], frame_with_detections["y"])
    cv2.imshow('Detections', frame_with_detections["frame"])
    cv2.waitKey(0)
    cv2.destroyAllWindows()
