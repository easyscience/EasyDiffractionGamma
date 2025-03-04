## Internal ED format for CIF datablocks

```json
{
  "data_": {
    "id": "lbco",
    "singles": {
      "_cell": {
        "length_a": 3.9,
        "length_b": 3.9,
        "length_c": 3.9,
        "angle_alpha": 90,
        "angle_beta": 90,
        "angle_gamma": 90
      },
      "_space_group": {
        "name_H-M_alt": "P m -3 m",
        "IT_coordinate_system_code": 1
      }
    },
    "tables": {
      "_atom_site": [
        {
          "label": "La",
          "type_symbol": "La",
          "fract_x": "0",
          "ADP_type": "Biso"
        },
        {
          "label": "Ba",
          "type_symbol": "Ba",
          "fract_x": "0",
          "ADP_type": "Biso"
        },
        {
          "label": "Co",
          "type_symbol": "Co",
          "fract_x": "0.5",
          "ADP_type": "Biso"
        },
        { "label": "O", "type_symbol": "O", "fract_x": "0", "ADP_type": "Biso" }
      ]
    }
  }
}
```

## Parameter name shortcuts

```
name                                                        value
----                                                        -----

model(lbco) _cell.length_a                                  3.9
model(lbco) _atom_site.fract_x(Co)                          0
exper(hrpt) _pd_phase_block.scale(lbco)                     1.43
exper(hrpt) _pd_background.line_segment_intensity(10)       200

lbco _cell.length_a                                         3.9
lbco _atom_site.fract_x Co                                  0
hrpt _pd_phase_block.scale lbco                             1.43
hrpt _pd_background.line_segment_intensity 10               200

lbco cell.a                                                 3.9
lbco atom.x Co                                              0
hrpt phase.scale lbco                                       1.43
hrpt bkg.intensity 10                                       200
```

## Possible description of constraints in CIF

```
loop_
_constr.id
_constr.ind_block_id
_constr.ind_parameter_id
_constr.ind_loop_key
_constr.dep_block_id
_constr.dep_parameter_id
_constr.dep_loop_key
_constr.multiplier
1 lbco _cell.length_a     .  cosio _cell.length_a     . 1       # lbco._cell.length_a = cosio._cell.length_a
2 lbco _atom_site.fract_x Co cosio _atom_site.fract_z O 0.3333  # lbco._atom_site.fract_x(Co) = cosio._atom_site.fract_z(O) * 0.3333
```
