import time

import cv2
import numpy as np
import onnxruntime as ort
import yaml

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from module.atom.click import RuleClick
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, HyakkiyakouAssets):

    def run(self):
        self.onnx_model = './tasks/Hyakkiyakou/weights/best.onnx'
        self.confidence_thres = 0.1
        self.iou_thres = 0.4

        # Load the class names from the COCO dataset
        with open('./tasks/Hyakkiyakou/data.yaml', 'r', encoding='utf-8') as file:
            self.classes = yaml.safe_load(file)['names']
        print(self.classes)

        # Generate a color palette for the classes
        self.color_palette = np.random.uniform(0, 255, size=(len(self.classes), 3))

        # Model
        # Create an inference session using the ONNX model and specify execution providers
        session = ort.InferenceSession(self.onnx_model, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])

        # Get the model inputs
        model_inputs = session.get_inputs()

        # Store the shape of the input for later use
        input_shape = model_inputs[0].shape
        self.input_width = input_shape[2]
        self.input_height = input_shape[3]

        n = 0
        self.screenshot()
        if self.appear_then_click(self.START):
            while 1:
                print('--------------------')
                start = time.time()
                start2 = time.time()
                self.screenshot()
                end2 = time.time()
                print('截图速度', end2 - start2)
                if self.appear(self.END):
                    break
                # Inference
                start1 = time.time()
                # Preprocess the image data
                self.input_image = self.device.image
                img_data = self.preprocess()

                # Run inference using the preprocessed image data
                outputs = session.run(None, {model_inputs[0].name: img_data})

                # Perform post-processing on the outputs to obtain output image.
                oasNeeds = self.postprocess(outputs)  # output image
                print(oasNeeds)
                # 过滤模型
                if oasNeeds:
                    rightPoint = []
                    n = n + 1
                    for oasNeeds in oasNeeds:
                        if not rightPoint:
                            rightPoint = [oasNeeds[0][0], oasNeeds[0][1], oasNeeds[0][2], oasNeeds[0][3]]
                        elif rightPoint[0] > oasNeeds[0][0]:
                            rightPoint = [oasNeeds[0][0], oasNeeds[0][1], oasNeeds[0][2], oasNeeds[0][3]]
                    end1 = time.time()
                    print('识别速度', end1 - start1)
                    if rightPoint:
                        click = RuleClick(roi_front=(rightPoint[0], rightPoint[1], rightPoint[2], rightPoint[3]),
                                          roi_back=(rightPoint[0], rightPoint[1], rightPoint[2], rightPoint[3]), name=n)
                        self.click(click)
                    end = time.time()
                    print('总速度', end - start)
                    print('--------------------')

    def preprocess(self):
        """
        Preprocesses the input image before performing inference.

        Returns:
            image_data: Preprocessed image data ready for inference.
        """
        # Read the input image using OpenCV
        self.img = self.input_image

        # Get the height and width of the input image
        self.img_height, self.img_width = self.img.shape[:2]

        # Convert the image color space from BGR to RGB
        img = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)

        # Resize the image to match the input shape
        img = cv2.resize(img, (self.input_width, self.input_height))

        # Normalize the image data by dividing it by 255.0
        image_data = np.array(img) / 255.0

        # Transpose the image to have the channel dimension as the first dimension
        image_data = np.transpose(image_data, (2, 0, 1))  # Channel first

        # Expand the dimensions of the image data to match the expected input shape
        image_data = np.expand_dims(image_data, axis=0).astype(np.float32)

        # Return the preprocessed image data
        return image_data

    def postprocess(self, output):
        """
        Performs post-processing on the model's output to extract bounding boxes, scores, and class IDs.

        Args:
            input_image (numpy.ndarray): The input image.
            output (numpy.ndarray): The output of the model.

        Returns:
            numpy.ndarray: The input image with detections drawn on it.
        """

        # Transpose and squeeze the output to match the expected shape
        outputs = np.transpose(np.squeeze(output[0]))

        # Get the number of rows in the outputs array
        rows = outputs.shape[0]

        # Lists to store the bounding boxes, scores, and class IDs of the detections
        boxes = []
        scores = []
        class_ids = []
        oasNeeds = []

        # Calculate the scaling factors for the bounding box coordinates
        x_factor = self.img_width / self.input_width
        y_factor = self.img_height / self.input_height

        # Iterate over each row in the outputs array
        for i in range(rows):
            # Extract the class scores from the current row
            classes_scores = outputs[i][4:]

            # Find the maximum score among the class scores
            max_score = np.amax(classes_scores)

            # If the maximum score is above the confidence threshold
            if max_score >= self.confidence_thres:
                # Get the class ID with the highest score
                class_id = np.argmax(classes_scores)

                # Extract the bounding box coordinates from the current row
                x, y, w, h = outputs[i][0], outputs[i][1], outputs[i][2], outputs[i][3]

                # Calculate the scaled coordinates of the bounding box
                left = int((x - w / 2) * x_factor)
                top = int((y - h / 2) * y_factor)
                width = int(w * x_factor)
                height = int(h * y_factor)

                # Add the class ID, score, and box coordinates to the respective lists
                class_ids.append(class_id)
                scores.append(max_score)
                boxes.append([left, top, width, height])

        # Apply non-maximum suppression to filter out overlapping bounding boxes
        indices = cv2.dnn.NMSBoxes(boxes, scores, self.confidence_thres, self.iou_thres)

        # Iterate over the selected indices after non-maximum suppression
        for i in indices:
            # Get the box, score, and class ID corresponding to the index
            box = boxes[i]
            score = scores[i]
            class_id = class_ids[i]

            # Draw the detection on the input image

            oasNeed = [box, score, self.classes[class_id]]
            oasNeeds.append(oasNeed)

        # Return the modified input image
        return oasNeeds


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
