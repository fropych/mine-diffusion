import launch

if not launch.is_installed("litemapy"):
    launch.run_pip("install litemapy==0.7.2b0", "requirements for Mine Diffusion")
if not launch.is_installed("numba"):
    launch.run_pip("install numba==0.56.4", "requirements for Mine Diffusion")