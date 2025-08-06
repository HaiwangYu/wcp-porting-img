#include <vector> 
#include <iostream>  // debug
void test(){
    bool flag_data = false;

    

    double m_sc_bottom_1_y;
    double m_sc_bottom_1_x;
    double m_sc_bottom_2_y;
    double m_sc_bottom_2_x;
    double m_sc_top_1_y;
    double m_sc_top_1_x;
    double m_sc_top_2_y;
    double m_sc_top_2_x;
    double m_sc_upstream_1_z;
    double m_sc_upstream_1_x;
    double m_sc_upstream_2_z;
    double m_sc_upstream_2_x;
    double m_sc_downstream_1_z;
    double m_sc_downstream_1_x;
    double m_sc_downstream_2_z;
    double m_sc_downstream_2_x;

    if (flag_data){
        std::cout << "Data Reco Fiducial Volume! " << std::endl;
        // data 
        m_sc_bottom_1_y = -116;
        m_sc_bottom_1_x = 80;

        m_sc_bottom_2_y = -99;
        m_sc_bottom_2_x = 256;

        m_sc_top_1_y = 116; // used to be 118 cm
        m_sc_top_1_x = 100;

        m_sc_top_2_y = 102; // used to be 103 cm
        m_sc_top_2_x = 256;

        m_sc_upstream_1_z = 0;
        m_sc_upstream_1_x = 120;

        m_sc_upstream_2_z = 11;
        m_sc_upstream_2_x = 256;

        m_sc_downstream_1_z = 1037;
        m_sc_downstream_1_x = 120;

        m_sc_downstream_2_z = 1026;
        m_sc_downstream_2_x = 256;
        } else {
        // MC
        std::cout << "MC Truth Fiducial Volume! " << std::endl;
        m_sc_bottom_1_y = -116;
        m_sc_bottom_1_x = 34;

        m_sc_bottom_2_y = -98;
        m_sc_bottom_2_x = 256;

        m_sc_top_1_y = 116;
        m_sc_top_1_x = 70;

        m_sc_top_2_y = 100;
        m_sc_top_2_x = 256;

        m_sc_upstream_1_z = 0;
        m_sc_upstream_1_x = 50;

        m_sc_upstream_2_z = 14;
        m_sc_upstream_2_x = 256;

        m_sc_downstream_1_z = 1037;
        m_sc_downstream_1_x = 40;

        m_sc_downstream_2_z = 1023;
        m_sc_downstream_2_x = 256;
        }

        //3*units::cm, 117*units::cm, -116*units::cm, 0*units::cm, 1037*units::cm, 0*units::cm, 256*units::cm,
        double boundary_dis_cut = 3;
        double m_anode = 0;
        double m_cathode = 256;
        double m_top = 117;
        double m_bottom = -116;
        double m_upstream = 0;
        double m_downstream = 1037;

        std::vector<double> boundary_xy_x;
        std::vector<double> boundary_xy_y;
        std::vector<double> boundary_xz_x;
        std::vector<double> boundary_xz_z;
        //
        boundary_xy_x.clear(); boundary_xy_y.clear();
        boundary_xy_x.push_back(m_anode + boundary_dis_cut); boundary_xy_y.push_back(m_bottom + boundary_dis_cut);
        boundary_xy_x.push_back(m_sc_bottom_1_x - boundary_dis_cut); boundary_xy_y.push_back(m_sc_bottom_1_y + boundary_dis_cut);
        boundary_xy_x.push_back(m_sc_bottom_2_x - boundary_dis_cut); boundary_xy_y.push_back(m_sc_bottom_2_y + boundary_dis_cut);
        boundary_xy_x.push_back(m_sc_top_2_x - boundary_dis_cut); boundary_xy_y.push_back(m_sc_top_2_y - boundary_dis_cut);
        boundary_xy_x.push_back(m_sc_top_1_x - boundary_dis_cut); boundary_xy_y.push_back(m_sc_top_1_y - boundary_dis_cut);
        boundary_xy_x.push_back(m_anode + boundary_dis_cut); boundary_xy_y.push_back(m_top - boundary_dis_cut);
        // boundary_xy_x.push_back(m_anode + boundary_dis_cut); boundary_xy_y.push_back(m_bottom + boundary_dis_cut);

        for (size_t i = 0; i != boundary_xy_x.size(); i++) {
            std::cout << boundary_xy_x.at(i) << " XY " << boundary_xy_y.at(i) << std::endl;
        }

        boundary_xz_x.clear(); boundary_xz_z.clear();
        boundary_xz_x.push_back(m_anode + boundary_dis_cut); boundary_xz_z.push_back(m_upstream + boundary_dis_cut + 1);
        boundary_xz_x.push_back(m_sc_upstream_1_x - boundary_dis_cut); boundary_xz_z.push_back(m_sc_upstream_1_z + boundary_dis_cut + 1);
        boundary_xz_x.push_back(m_sc_upstream_2_x - boundary_dis_cut); boundary_xz_z.push_back(m_sc_upstream_2_z + boundary_dis_cut + 1);
        boundary_xz_x.push_back(m_sc_downstream_2_x - boundary_dis_cut); boundary_xz_z.push_back(m_sc_downstream_2_z - boundary_dis_cut - 1);
        boundary_xz_x.push_back(m_sc_downstream_1_x - boundary_dis_cut); boundary_xz_z.push_back(m_sc_downstream_1_z - boundary_dis_cut - 1);
        boundary_xz_x.push_back(m_anode + boundary_dis_cut); boundary_xz_z.push_back(m_downstream - boundary_dis_cut - 1);
        // boundary_xz_x.push_back(m_anode + boundary_dis_cut); boundary_xz_z.push_back(m_upstream + boundary_dis_cut + 2);

        for (size_t i = 0; i != boundary_xz_x.size(); i++) {
            std::cout << boundary_xz_x.at(i) << " XZ " << boundary_xz_z.at(i) << std::endl;
        }
}