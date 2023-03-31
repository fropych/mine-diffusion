from functools import lru_cache

import numpy as np
from litemapy import BlockState, Region
from PIL import Image
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
        self._Region__palette = [
            AIR,
        ]
        self.__palette_ids = [
            AIR.blockid + str(AIR.properties),
        ]

    def setblock(self, x, y, z, block):
        x, y, z = self._Region__regcoordinates2storecoords(x, y, z)
        if block.blockid + str(block.properties) in self.__palette_ids:
            i = self.__palette_ids.index(block.blockid + str(block.properties))
        else:
            self._Region__palette.append(block)
            self.__palette_ids.append(block.blockid + str(block.properties))
            i = len(self._Region__palette) - 1
        self._Region__blocks[x, y, z] = i

@njit(fastmath=True)
def _img_to_bcolors_jit(rgb_matrix, img, outp_ids, dithering):
    ditheringMatrix = ((1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1))
    ditheringScaleFactor = 16.0
    
    width = img.shape[1]
    height = img.shape[0]
    for y in range(height):
        for x in range(width):
        
            matrix = rgb_matrix - img[y][x]
            matrix *= matrix
            best_match = matrix.sum(-1).argmin()
            outp_ids[y][x] = best_match
            best_match = rgb_matrix[best_match]

            if dithering:
                differenceRGB = [0, 0, 0]
                for channel in range(3):
                    differenceRGB[channel] = img[y][x][channel] - best_match[channel]

                for i in range(len(ditheringMatrix)):
                    xOffset = ditheringMatrix[i][0]
                    yOffset = ditheringMatrix[i][1]
                    if (
                        x + xOffset < width
                        and x + xOffset >= 0
                        and y + yOffset < height
                        and y + yOffset >= 0
                    ):
                        nextRGB = img[y + yOffset][x + xOffset]
                        for channel in range(3):
                            nextRGB[channel] = int(min((
                                max(
                                    (
                                        (
                                            nextRGB[channel]
                                            + differenceRGB[channel]
                                            * ditheringMatrix[i][2]
                                            / ditheringScaleFactor
                                        ),
                                        0,
                                    )
                                ),
                                255)
                            ))

class BColor:
    def __init__(self, id, rgb, blocks) -> None:
        self.id = id
        self.rgb = rgb["normal"]
        self.blocks = self._get_blocks(blocks)

    def _get_blocks(self, blocks):
        converted_blocks = []
        for key, value in blocks.items():
            converted_blocks.append(
                Block(
                    int(key), value["NBTName"], value["displayName"], value["NBTArgs"]
                )
            )
        return converted_blocks


class Block:
    def __init__(self, id, name, display_name, properties=None):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.properties = properties
        self.horizontal = False

    def __repr__(self):
        return f"Block({self.id}, {self.name}, {self.texture}, {self.rgb}, {self.a})"


class ImgToBlocks:
    def __init__(self, bcolors):
        self.bcolors = bcolors
        self.rgb_matrix = np.array(
            [color.rgb for color in self.bcolors], dtype=np.int32
        )

    def _img_to_bcolors(self, img, outp_ids, dithering):
        img = img
        rgb_matrix = self.rgb_matrix
        outp = _img_to_bcolors_jit(rgb_matrix, img, outp_ids, dithering)
        return outp

    def __call__(self, img, dithering):
        shape = img.shape
        img = img.astype(np.float32)
        outp_ids = np.empty(shape[:2], np.uint16)
        self._img_to_bcolors(img, outp_ids, dithering)
        return outp_ids

    @lru_cache()
    def get_texture(self, texture, textures_dir):
        texture_path = textures_dir / f"{texture}.png"
        img = Image.open(texture_path).convert("RGBA")
        return np.array(img, dtype=np.uint8)

    def image(self, img, compressed_size=None, dithering=False):
        shape = img.shape
        bcolors_id = self(img, dithering)
        outp_img = np.empty(shape[:2], dtype=np.uint8).tolist()
        for i in range(shape[0]):
            for j in range(shape[1]):
                color = self.bcolors[bcolors_id[i][j]].rgb
                outp_img[i][j] = color

        img = Image.fromarray(np.array(outp_img, dtype=np.uint8))
        if compressed_size is not None:
            img = img.resize(compressed_size)
        return img


class ImgToSchematic:
    axis_change = {
        "x": "y",
        "y": "x",
    }

    def __init__(self, bcolors):
        self.block_names = []
        self.bcolors = []
        for bcolor_id, bcolor_value in bcolors.items():
            self.bcolors.append(
                BColor(bcolor_id, bcolor_value["tonesRGB"], bcolor_value["blocks"])
            )
            for block in bcolor_value["blocks"].values():
                self.block_names.append(block["displayName"])

    def prepare_image(self, img, width, height):
        img = img.resize((width, height))
        img = np.array(img, dtype=np.uint8)
        return img

    def parse_blacklist(self, blacklist):
        bcolors = []
        blacklist = set(blacklist)

        for bcolor in self.bcolors:
            new_blocks = []
            for block in bcolor.blocks:
                if block.display_name not in blacklist:
                    new_blocks.append(block)
            if new_blocks:
                bcolor.blocks = new_blocks
                bcolors.append(bcolor)
        return bcolors

    def get_img2blocks(self, blacklist=None):
        if blacklist is None:
            blacklist = set()
        img2blocks = ImgToBlocks(self.parse_blacklist(blacklist))
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
        dithering=False,
    ):
        img = self.prepare_image(img, width, height)
        if (not flip) or (flip and vertical):
            img = np.flip(img, axis=1)
        if rotate_angle:
            img = np.rot90(img, -rotate_angle // 90)

        img2blocks = self.get_img2blocks(blacklist)
        bcolors = img2blocks.bcolors

        bcolors_id = img2blocks(img, dithering)
        if not vertical:
            reg = FastRegion(0, 0, 0, width, 1, height)
            for x, y, z in reg.allblockpos():
                block = bcolors[bcolors_id[z][width - 1 - x]].blocks[0]
                block = FastBlockState(block.name, block.properties)
                reg.setblock(x, y, z, block)
        else:
            reg = FastRegion(0, 0, 0, width, height, 1)
            for x, y, z in reg.allblockpos():
                block = bcolors[bcolors_id[height - 1 - y][x]].blocks[0]
                block = FastBlockState(block.name, block.properties)
                reg.setblock(x, y, z, block)

        schem = reg.as_schematic(
            name=name, author="sb", description="Made with img2schem"
        )
        return schem

    def get_image(
        self, img, width, height, blacklist=None, compressed_size=None, dithering=False
    ):
        img = self.prepare_image(img, width, height)

        img2blocks = self.get_img2blocks(blacklist)
        return img2blocks.image(img, compressed_size, dithering)
