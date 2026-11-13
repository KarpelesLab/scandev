// capture -- adds each shot's samples into a memory, sample by sample.
//
// The write address restarts at every shot and advances on every sample
// taken while `acquire` is high, so several acquisition windows in one shot
// (an echo train) land one after another.  After `clear`, the next shot
// overwrites instead of adding, which empties the memory without a sweep.
//
// A sample takes three cycles to add, so samples must be at least four
// cycles apart; the down-converter's smallest decimation is larger than that
// in any useful setting.
module capture #(
    parameter AW = 11
) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 clear,
    input  wire                 shot_start,
    input  wire                 acquire,
    input  wire                 valid,
    input  wire signed   [31:0] i,
    input  wire signed   [31:0] q,
    output reg         [AW:0]   count,      // samples in the last/current shot

    input  wire        [AW-1:0] rd_addr,    // host read, when not capturing
    output wire signed   [31:0] rd_i,
    output wire signed   [31:0] rd_q
);
    reg [63:0] mem [0:(1<<AW)-1];
    reg [63:0] mem_q;

    reg          overwrite;     // the shot in progress replaces the contents
    reg          pend_clear;
    reg    [1:0] ph;            // 0 idle, 1 read issued, 2 data out, write
    reg [AW-1:0] wa;
    reg signed [31:0] si, sq;

    wire take = valid && acquire && !count[AW];
    wire [AW-1:0] ra = (ph != 2'd0) ? wa : rd_addr;

    wire signed [31:0] old_i = mem_q[63:32];
    wire signed [31:0] old_q = mem_q[31:0];
    wire signed [31:0] new_i = overwrite ? si : old_i + si;
    wire signed [31:0] new_q = overwrite ? sq : old_q + sq;
    wire we = (ph == 2'd2);

    always @(posedge clk) begin
        if (we) mem[wa] <= {new_i, new_q};
        mem_q <= mem[ra];
    end

    assign rd_i = mem_q[63:32];
    assign rd_q = mem_q[31:0];

    always @(posedge clk) begin
        if (rst) begin
            ph <= 2'd0;
            count <= 0;
            overwrite <= 1'b1;
            pend_clear <= 1'b0;
        end else begin
            if (clear) pend_clear <= 1'b1;
            if (shot_start) begin
                count      <= 0;
                overwrite  <= pend_clear;
                pend_clear <= 1'b0;
            end
            case (ph)
                2'd0: if (take) begin
                    wa <= count[AW-1:0];
                    si <= i;
                    sq <= q;
                    count <= count + 1'b1;
                    ph <= 2'd1;
                end
                2'd1: ph <= 2'd2;
                default: ph <= 2'd0;
            endcase
        end
    end

    initial begin
        ph = 0; count = 0; overwrite = 1; pend_clear = 0; wa = 0; si = 0; sq = 0;
        mem_q = 0;
    end
endmodule
