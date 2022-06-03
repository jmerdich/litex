#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jake Merdich <jake@merdich.com>
# SPDX-License-Identifier: MIT

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = [
    "standard",
]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /-------- Base ISA
    #                               |/------- Hardware Multiply + Divide
    #                               ||/----- Atomics
    #                               |||/---- Compressed ISA
    #                               ||||/--- Single-Precision Floating-Point
    #                               |||||/-- Double-Precision Floating-Point
    #                               imacfd
    "standard":         "-march=rv32i      -mabi=ilp32 ",
}

# MrCpu -----------------------------------------------------------------------------------------

def GenMasterStall(iface):
    # MrCpu uses pipelined wishbone, but litex uses classic
    # Bridge the gap.
    return iface.cyc & ~iface.ack

class MrCpu(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "mrcpu"
    human_name           = "MrCPU"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-mno-save-restore "
        flags += GCC_FLAGS[self.variant]
        return flags


    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus        = ibus = wishbone.Interface()
        self.dbus        = dbus = wishbone.Interface()
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # # #

        # Parameters, change the desired parameters to create a create a new variant.
        self.cpu_params = dict(
        )

        self.cpu_params.update(
            # Clk / Rst.
            i_clk = ClockSignal("sys"),
            i_rst = (ResetSignal("sys") | self.reset),

            # Memory Interface.
            o_wbm0_adr_o   = ibus.adr,
            i_wbm0_dat_i   = ibus.dat_r,
            o_wbm0_dat_o   = ibus.dat_w,
            o_wbm0_we_o    = ibus.we,
            o_wbm0_sel_o   = ibus.sel,
            o_wbm0_stb_o   = ibus.stb,
            i_wbm0_ack_i   = ibus.ack,
            i_wbm0_err_i   = ibus.err,
            o_wbm0_cyc_o   = ibus.cyc,
            i_wbm0_stall_i = GenMasterStall(ibus),

            o_wbm1_adr_o   = dbus.adr,
            i_wbm1_dat_i   = dbus.dat_r,
            o_wbm1_dat_o   = dbus.dat_w,
            o_wbm1_we_o    = dbus.we,
            o_wbm1_sel_o   = dbus.sel,
            o_wbm1_stb_o   = dbus.stb,
            i_wbm1_ack_i   = dbus.ack,
            i_wbm1_err_i   = dbus.err,
            o_wbm1_cyc_o   = dbus.cyc,
            i_wbm1_stall_i = GenMasterStall(dbus)
        )

        # Add Verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(
            #p_PROGADDR_RESET = reset_address,
            #p_PROGADDR_IRQ   = reset_address + 0x00000010
        )

    @staticmethod
    def add_sources(platform):
        if "MRCPU_SOURCE_OVERLAY" in os.environ:
            # Special path to use sources directly instead of through package
            vdir = os.environ["MRCPU_SOURCE_OVERLAY"]
        else:
            vdir = get_data_mod("cpu", "mrcpu").data_location
        platform.add_verilog_include_path(os.path.join(vdir, "rtl"))
        platform.add_verilog_include_path(vdir)
        platform.add_source_dir(os.path.join(vdir, "rtl"))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("mr_core", **self.cpu_params)
