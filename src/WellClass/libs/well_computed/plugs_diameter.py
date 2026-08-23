from typing import Any, Dict, List



def compute_plugs_diameter(plugs:List[Dict[str,Any]], borehole:List[Dict[str,Any]]) -> List[Dict[str,Any]]:

    plugs_processed = []

    for plug in plugs:
        plug_name = plug['name']
        plug_top = plug['top_rkb']
        plug_bottom = plug['bottom_rkb']
        plug_cement_perm = plug.get('cement_perm', None)
        plug_top_tvdmsl = plug['tvd_msl_top']
        plug_bottom_tvdmsl = plug['tvd_msl_bottom']


        # Find borehole sections that overlap with the plug
        borehole_plug_top = [bh for bh in borehole if bh['top_rkb'] <= plug_top <= bh['bottom_rkb']]
        borehole_plug_bottom = [bh for bh in borehole if bh['top_rkb'] <= plug_bottom <= bh['bottom_rkb']]

        # Cement plug intervals should be defined within the borehole sections, if these return empty, data must be wrong
        if not borehole_plug_top or not borehole_plug_bottom:
            raise ValueError(f"Plug '{plug_name}' has top or bottom intervals that do not overlap with any borehole sections. Please check the data.")
            
        borehole_plug_top_diameter = borehole_plug_top[0]['diameter_m']
        borehole_plug_bottom_diameter = borehole_plug_bottom[0]['diameter_m']

        if borehole_plug_top_diameter == borehole_plug_bottom_diameter:
            plugs_processed.append({
                'name': plug_name,
                'segment':0,

                'top_rkb': plug_top,
                'bottom_rkb': plug_bottom,
                'top_tvd_msl': plug_top_tvdmsl,
                'bottom_tvd_msl': plug_bottom_tvdmsl,
                'diameter_m': borehole_plug_top_diameter,
                'cement_perm': plug_cement_perm
            })
        
        else:
            borehole_subsections = [bh for bh in borehole if borehole_plug_bottom_diameter <= bh['diameter_m'] <= borehole_plug_top_diameter]

            for idx, subsection in enumerate(borehole_subsections):
                plugs_processed.append({
                    'name': plug_name,
                    'segment': idx,
                    'top_rkb': max(plug_top, subsection['top_rkb']),
                    'bottom_rkb': min(plug_bottom, subsection['bottom_rkb']),
                    'top_tvd_msl': max(plug_top_tvdmsl, subsection['top_tvd_msl']),
                    'bottom_tvd_msl': min(plug_bottom_tvdmsl, subsection['bottom_tvd_msl']),
                    'diameter_m': subsection['diameter_m'],
                    'cement_perm': plug_cement_perm
                })

    return plugs_processed
