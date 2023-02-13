from functools import lru_cache
from copy import deepcopy

import numpy as np
from litemapy import BlockState, Region
from PIL import Image
import torch
from numba import njit

class FastBlockState(BlockState):
    def __init__(self, blockid, properties=None) -> None:
        super().__init__(blockid, properties)
        
    @property
    def properties(self):
        return self._BlockState__properties
    
AIR = FastBlockState("minecraft:air")
class FastRegion(Region):
    
    def __init__(self, x, y, z, width, height, length) -> None:
        super().__init__(x, y, z, width, height, length)
        self._Region__palette = [AIR, ]
        self.__palette_ids = [AIR.blockid + str(AIR.properties), ]
    
    def setblock(self, x, y, z, block):
        x, y, z = self._Region__regcoordinates2storecoords(x, y, z)
        if block.blockid+str(block.properties) in self.__palette_ids:
            i = self.__palette_ids.index(block.blockid+str(block.properties))
        else:
            self._Region__palette.append(block)
            self.__palette_ids.append(block.blockid+str(block.properties))
            i = len(self._Region__palette) - 1
        self._Region__blocks[x, y, z] = i      
        
@njit(fastmath=True)
def _img_to_blocks_jit(rgb_matrix, img):
    outp = []
    for pixel in img:
        x = rgb_matrix-pixel
        x *=x
        x = x.sum(-1).argmin()
        outp.append(x)
    return outp

class Block:
    def __init__(self, id, name, texture, rgb, a=255, properties=None):
        self.id = id
        self.name = name
        self.texture = texture
        self.rgb = rgb
        self.a = a
        self.properties = properties
        self.horizontal = False

    def __repr__(self):
        return f"Block({self.id}, {self.name}, {self.texture}, {self.rgb}, {self.a})"

class ImgToBlocks:
    def __init__(self, blocks):
        self.blocks = blocks
        self.rgb_matrix = np.array([block.rgb for block in self.blocks], dtype=np.int32)

    def _img_to_blocks(self, img, jit=False):
        if jit:
            img = img
            rgb_matrix = self.rgb_matrix
            outp = _img_to_blocks_jit(rgb_matrix, img)
            return outp
        
        img = torch.Tensor(img[:, None, :])
        rgb_matrix = torch.Tensor(self.rgb_matrix[None, :, :])
        x = torch.norm(rgb_matrix-img, dim=-1, p=2)
        outp = x.argmin(-1)
        return outp.tolist()
        
    def pixel_to_block(self, pixel):
        block = self.blocks[
            np.argmin(np.linalg.norm(self.rgb_matrix - pixel, axis=1, ord=2))
        ]
        return deepcopy(block)

    def __call__(self, img, jit):
        shape = img.shape
        img = img.reshape(-1, 3)
        blocks = self._img_to_blocks(img, jit)
        blocks = np.array([self.blocks[block] for block in blocks]).reshape(shape[:2])
        return blocks.tolist()

    @lru_cache()
    def get_texture(self, texture, textures_dir):
        texture_path = textures_dir / f"{texture}.png"
        img = Image.open(texture_path).convert("RGBA")
        return np.array(img, dtype=np.uint8)

    def image(self, img, textures_dir, compressed_size=None, jit=False):
        shape = img.shape
        blocks = self(img, jit)
        textures = np.empty(shape[:2], dtype=np.uint8).tolist()
        for i in range(shape[0]):
            for j in range(shape[1]):
                texture = blocks[i][j].texture
                texture = self.get_texture(texture, textures_dir)
                textures[i][j] = texture

        rows = []
        for i in range(len(textures)):
            row = np.hstack(textures[i])
            rows.append(row)
        img = Image.fromarray(np.vstack(rows))
        if compressed_size is not None:
            img = img.resize(compressed_size)
        return img


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
        jit=False,
    ):
        img = self.prepare_image(img, width, height)
        if (not flip) or (flip and vertical):
            img = np.flip(img, axis=1)
        if rotate_angle:
            img = np.rot90(img, -rotate_angle // 90)

        img2blocks = self.get_img2blocks(blacklist)

        blocks_scheme = img2blocks(img, jit)
        if not vertical:
            reg = FastRegion(0, 0, 0, width, 1, height)
            for x, y, z in reg.allblockpos():
                block = blocks_scheme[z][width - 1 - x]
                if block.properties.get("axis") is not None and not block.horizontal:
                    block.properties["axis"] = self.axis_change[
                        block.properties["axis"]
                    ]
                    block.horizontal = True
                block = FastBlockState(block.name, block.properties)
                reg.setblock(x, y, z, block)
        else:
            reg = FastRegion(0, 0, 0, width, height, 1)
            for x, y, z in reg.allblockpos():
                block = blocks_scheme[height - 1 - y][x]
                block = FastBlockState(block.name, block.properties)
                reg.setblock(x, y, z, block)

        schem = reg.as_schematic(
            name=name, author="sb", description="Made with img2schem"
        )
        return schem

    def get_image(self, img, width, height, textures_dir, blacklist=None, compressed_size=None, jit=False):
        img = self.prepare_image(img, width, height)

        img2blocks = self.get_img2blocks(blacklist)
        return img2blocks.image(img, textures_dir, compressed_size, jit)
