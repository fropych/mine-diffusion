import json
from pathlib import Path

import gradio as gr
from img2schem import ImgToSchematic
from modules import script_callbacks, shared


EXT_DIR = Path(__file__).parent.parent
TEXTURES_DIR = EXT_DIR / "textures"

with open(EXT_DIR / "blocks.json", "r") as f:
    blocks = json.load(f)
img2schem = ImgToSchematic(blocks)

with open(EXT_DIR / "blacklists/Base.txt", "r") as f:
    blacklist = set([name.strip() for name in f.readlines()])
blacklist_presets = Path(EXT_DIR / "blacklists").glob("*.txt")


def save_schem(img, width, height, vertical, flip, rotate_angle, path, name, jit):
    shared.opts.schem_path = path
    path = Path(path) / f"{name}.litematic"
    schem = img2schem(img, width, height, vertical, flip, rotate_angle, name, blacklist, jit)
    schem.save(path)


def preview(img, width, height, jit):
    return img2schem.get_image(img, width, height, TEXTURES_DIR, blacklist, jit=jit)


def blacklist_handler(blacklist_presets_dd, blacklist_dd, action):
    if len(blacklist_presets_dd) == 0:
        return blacklist_dd

    with open(
        EXT_DIR / f"blacklists/{blacklist_presets_dd}.txt", "rb"
    ) as blacklist_txt:
        blacklist_txt = [
            line.decode("utf-8", "ignore").strip() for line in blacklist_txt.readlines()
        ]
    if action == "add":
        blacklist_dd += blacklist_txt
    elif action == "exclude":
        blacklist_dd = [i for i in blacklist_dd if i not in blacklist_txt]
    elif action == "replace":
        blacklist_dd = blacklist_txt
    return set(blacklist_dd)


def blacklist_update(blacklist_dd):
    global blacklist
    blacklist = set(blacklist_dd)


def blacklist_presets_update():
    blacklist_presets = Path(EXT_DIR / "blacklists").glob("*.txt")
    return gr.Dropdown.update(choices=[preset.stem for preset in blacklist_presets])


def blacklist_save(blacklist_dd, name):
    with open(EXT_DIR / f"blacklists/{name}.txt", "w") as f:
        f.write("\n".join(blacklist_dd))


def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as aesthetic_interface:
        with gr.Tab("Main"):
            with gr.Row():
                with gr.Column(variant="panel"):
                    img = gr.Image(type="pil")
                    gr.Markdown("### Schematic Settings")
                    with gr.Row(variant="compact"):
                        with gr.Column(scale=0.3, min_width=140):
                            gr.Markdown("#### Orientation")
                            vertical = gr.Checkbox(
                                value=False, label="Vertical", interactive=True
                            )
                            flip = gr.Checkbox(
                                value=False, label="Flip", interactive=True
                            )
                            rotate_angle = gr.Dropdown(
                                [-180, -90, 0, 90, 180],
                                label="Rotation",
                                value=0,
                                interactive=True,
                            )
                        with gr.Column(scale=3):
                            gr.Markdown("#### Schematic Size")
                            width = gr.Slider(
                                label="Width",
                                value=128,
                                minimum=32,
                                maximum=1024,
                                step=2,
                                interactive=True,
                            )
                            height = gr.Slider(
                                label="Height",
                                value=128,
                                minimum=32,
                                maximum=1024,
                                step=2,
                                interactive=True,
                            )
                            jit = gr.Checkbox(
                                value=False, label="Reduce Memory Usage", interactive=True
                            )
                    gr.Markdown("### Save Schematic")
                    schem_type = gr.Radio(
                        ["litematic", "schematic(in development)"],
                        value="litematic",
                        label="Type",
                        interactive=False,
                    )
                    path = gr.Textbox(
                        lines=1,
                        label="Path to Schematics Folder",
                        value=shared.opts.schem_path,
                    )
                    name = gr.Textbox(
                        lines=1,
                        label="Schematic Name",
                        value="test",
                    )

                    with gr.Row():
                        save_bn = gr.Button(value="Save Schematic", variant="primary")
                        preview_bn = gr.Button(value="Preview", variant="primary")

                with gr.Column(scale=0.5):
                    converted_img = gr.Image(interactive=False)

            save_bn.click(
                fn=save_schem,
                inputs=[
                    img,
                    width,
                    height,
                    vertical,
                    flip,
                    rotate_angle,
                    path,
                    name,
                    jit
                ],
            )

            preview_bn.click(
                fn=preview,
                inputs=[
                    img,
                    width,
                    height,
                    jit,
                ],
                outputs=[converted_img],
            )

        with gr.Tab("Blocks Blacklist"):
            with gr.Row():
                with gr.Column(scale=0.3, min_width=250):
                    action = gr.Radio(
                        ["add", "exclude", "replace"], value="replace", label="Action"
                    )
                    blacklist_presets_dd = gr.Dropdown(
                        [preset.stem for preset in blacklist_presets],
                        label="Blacklist Presets",
                        value="Base",
                        interactive=True,
                    )
                    with gr.Row():
                        load_bn = gr.Button("Load")
                        apply_bn = gr.Button("Apply", variant="primary")
                        update_blacklist_presets_bn = gr.Button("Update Presets")
                    blacklist_name = gr.Textbox(
                        lines=1,
                        label="Blacklist Name",
                    )
                    save_blacklist_bn = gr.Button("Save Blacklist")
                with gr.Column():
                    blacklist_dd = gr.Dropdown(
                        choices=img2schem.block_names,
                        value=list(blacklist),
                        multiselect=True,
                        label="Blacklist",
                        interactive=True,
                    )
            load_bn.click(
                fn=blacklist_handler,
                inputs=[blacklist_presets_dd, blacklist_dd, action],
                outputs=[blacklist_dd],
            )
            apply_bn.click(fn=blacklist_update, inputs=[blacklist_dd])
            update_blacklist_presets_bn.click(
                fn=blacklist_presets_update, outputs=[blacklist_presets_dd]
            )
            save_blacklist_bn.click(
                fn=blacklist_save, inputs=[blacklist_dd, blacklist_name]
            )
    return [(aesthetic_interface, "Mine Diffusion", "Mine Diffusion")]


def on_ui_settings():
    option = shared.options_section(
        ("ais", "Mine Diffusion"),
        {
            "schem_path": shared.OptionInfo(
                "YOUR_PATH/.minecraft/schematics",
                "Last schemtatics dir path",
                gr.Textbox,
                {"lines": 1},
            )
        },
    )

    shared.opts.add_option("schem_path", option["schem_path"])


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_ui_tabs(on_ui_tabs)
