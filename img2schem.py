from functools import lru_cache
from copy import deepcopy

import numpy as np
from litemapy import BlockState, Region
from PIL import Image


class Block:
    def __init__(self, id, name, texture, rgb, a=255, properties=None):
        self.id = id
        self.name = name
        self.texture = texture
        self.rgb = rgb
        self.a = a
        self.properties = properties

    def __repr__(self):
        return f"Block({self.id}, {self.name}, {self.texture}, {self.rgb}, {self.a})"


class ImgToBlocks:
    def __init__(self, blocks):
        self.blocks = blocks
        self.rgb_matrix = np.array([block.rgb for block in self.blocks], dtype=np.int32)

    def pixel_to_block(self, pixel):
        block = self.blocks[
            np.argmin(np.linalg.norm(self.rgb_matrix - pixel, axis=1, ord=2))
        ]
        return deepcopy(block)

    def __call__(self, img):
        return [[self.pixel_to_block(pixel) for pixel in row] for row in img]

    @lru_cache()
    def get_texture(self, texture, textures_dir):
        texture_path = textures_dir / f"{texture}.png"
        img = Image.open(texture_path).convert("RGBA")
        return np.array(img, dtype=np.uint8)

    def image(self, img, textures_dir):
        img_shape = img.shape
        textures = np.empty(img_shape[:2], dtype=np.uint8).tolist()
        for i, row in enumerate(img):
            for j, pixel in enumerate(row):
                texture = self.pixel_to_block(pixel).texture
                texture = self.get_texture(texture, textures_dir)
                textures[i][j] = texture

        rows = []
        for i in range(len(textures)):
            row = np.hstack(textures[i])
            rows.append(row)

        return Image.fromarray(np.vstack(rows))


class ImgToSchematic:
    axis_change = {
        "x": "y",
        "y": "x",
    }

    def __init__(self, blocks):
        self.blocks = []
        self.block_names = []
        for block in blocks:
            self.blocks.append(Block(**block))
            self.block_names.append(block["name"])

    def prepare_image(self, img, width, height):
        img = img.resize((width, height))
        img = np.array(img, dtype=np.uint8)
        return img

    def get_img2blocks(self, blacklist=None):
        if blacklist is None:
            blacklist = set()
        img2blocks = ImgToBlocks(
            [block for block in self.blocks if block.name not in blacklist]
        )
        return img2blocks

    def __call__(
        self,
        img,
        width,
        height,
        vertical=False,
        flip=False,
        rotate_angle=0,
        name="my_schematic",
        blacklist=None,
    ):
        img = self.prepare_image(img, width, height)
        if (not flip) or (flip and vertical):
            img = np.flip(img, axis=1)
        if rotate_angle:
            img = np.rot90(img, -rotate_angle // 90)

        img2blocks = self.get_img2blocks(blacklist)

        blocks_scheme = img2blocks(img)

        if not vertical:
            reg = Region(0, 0, 0, width, 1, height)
            for x, y, z in reg.allblockpos():
                block = blocks_scheme[z][width - 1 - x]
                if block.properties.get("axis") is not None:
                    block.properties["axis"] = self.axis_change[
                        block.properties["axis"]
                    ]
                block = BlockState(block.name, block.properties)
                reg.setblock(x, y, z, block)
        else:
            reg = Region(0, 0, 0, width, height, 1)
            for x, y, z in reg.allblockpos():
                block = blocks_scheme[height - 1 - y][x]
                block = BlockState(block.name, block.properties)
                reg.setblock(x, y, z, block)

        schem = reg.as_schematic(
            name=name, author="sb", description="Made with img2schem"
        )
        return schem

    def get_image(self, img, width, height, textures_dir, blacklist=None):
        img = self.prepare_image(img, width, height)

        img2blocks = self.get_img2blocks(blacklist)
        return img2blocks.image(img, textures_dir)
