// ROOT script to analyze cluster coverage distances with enhanced information
// Usage: root -l analyze_cluster_distances.C

#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include "TFile.h"
#include "TTree.h"
#include "TH1F.h"
#include "TH2F.h"
#include "TCanvas.h"
#include "TStyle.h"
#include "TLegend.h"
#include "TPaveText.h"
#include "TString.h"
#include "TProfile.h"

void cluster_distance(const char* input_file = "cluster_coverage_distances.txt") {
    
    // Set ROOT style
    gStyle->SetOptStat(1111);
    gStyle->SetOptFit(1111);
    gStyle->SetPalette(1);
    
    // Create output ROOT file
    TFile* outfile = new TFile("cluster_coverage_analysis.root", "RECREATE");
    
    // Create TTree to store the data
    TTree* tree = new TTree("coverage_tree", "Enhanced Cluster Coverage Analysis Tree");
    
    // Define branch variables for enhanced format
    Int_t cluster1_id, cluster2_id;
    Char_t coverage_plane[2];  // U, V, or W
    Float_t nearest_3d_distance_cm;
    Float_t nearest_2d_distance_cm;         // NEW
    Float_t cluster1_length_cm;             // NEW  
    Float_t cluster2_length_cm;             // NEW
    Int_t cluster1_time_min, cluster1_time_max;  // NEW
    Int_t cluster2_time_min, cluster2_time_max;  // NEW
    Int_t covered_points, total_points;
    Float_t coverage_ratio;
    
    // Create branches
    tree->Branch("cluster1_id", &cluster1_id, "cluster1_id/I");
    tree->Branch("cluster2_id", &cluster2_id, "cluster2_id/I");
    tree->Branch("coverage_plane", coverage_plane, "coverage_plane/C");
    tree->Branch("nearest_3d_distance_cm", &nearest_3d_distance_cm, "nearest_3d_distance_cm/F");
    tree->Branch("nearest_2d_distance_cm", &nearest_2d_distance_cm, "nearest_2d_distance_cm/F");  // NEW
    tree->Branch("cluster1_length_cm", &cluster1_length_cm, "cluster1_length_cm/F");              // NEW
    tree->Branch("cluster2_length_cm", &cluster2_length_cm, "cluster2_length_cm/F");              // NEW
    tree->Branch("cluster1_time_min", &cluster1_time_min, "cluster1_time_min/I");                 // NEW
    tree->Branch("cluster1_time_max", &cluster1_time_max, "cluster1_time_max/I");                 // NEW
    tree->Branch("cluster2_time_min", &cluster2_time_min, "cluster2_time_min/I");                 // NEW
    tree->Branch("cluster2_time_max", &cluster2_time_max, "cluster2_time_max/I");                 // NEW
    tree->Branch("covered_points", &covered_points, "covered_points/I");
    tree->Branch("total_points", &total_points, "total_points/I");
    tree->Branch("coverage_ratio", &coverage_ratio, "coverage_ratio/F");
    
    // Open input file
    std::ifstream infile(input_file);
    if (!infile.is_open()) {
        std::cerr << "Error: Cannot open input file " << input_file << std::endl;
        return;
    }
    
    std::string line;
    int line_count = 0;
    int data_entries = 0;
    
    std::cout << "Reading enhanced data from " << input_file << std::endl;
    
    // Read the file line by line
    while (std::getline(infile, line)) {
        line_count++;
        
        // Skip comment lines (starting with #)
        if (line.empty() || line[0] == '#') {
            continue;
        }
        
        // Parse the enhanced data line
        std::istringstream iss(line);
        std::string plane_str;
        
        // Parse enhanced format: cluster1_id cluster2_id coverage_plane nearest_3d_distance_cm nearest_2d_distance_cm 
        // cluster1_length_cm cluster2_length_cm cluster1_time_min cluster1_time_max cluster2_time_min 
        // cluster2_time_max covered_points total_points coverage_ratio
        if (iss >> cluster1_id >> cluster2_id >> plane_str >> nearest_3d_distance_cm >> nearest_2d_distance_cm
               >> cluster1_length_cm >> cluster2_length_cm >> cluster1_time_min >> cluster1_time_max 
               >> cluster2_time_min >> cluster2_time_max >> covered_points >> total_points >> coverage_ratio) {
            
            // Convert plane string to char
            strcpy(coverage_plane, plane_str.c_str());
            
            // Fill the tree
            tree->Fill();
            data_entries++;
            
            if (data_entries % 100 == 0) {
                std::cout << "Processed " << data_entries << " entries..." << std::endl;
            }
        } else {
            std::cerr << "Warning: Could not parse line " << line_count << ": " << line << std::endl;
        }
    }
    
    infile.close();
    std::cout << "Successfully read " << data_entries << " data entries from " << line_count << " lines." << std::endl;
    
    // Create enhanced histograms
    std::cout << "Creating enhanced histograms..." << std::endl;
    
    // 3D Distance histograms
    TH1F* h_distance_3d_all = new TH1F("h_distance_3d_all", "Nearest 3D Distance Between Covered Clusters;Distance (cm);Entries", 
                                       100, 0, 50);
    h_distance_3d_all->SetLineColor(kBlue);
    h_distance_3d_all->SetFillColor(kBlue);
    h_distance_3d_all->SetFillStyle(3004);
    
    // NEW: 2D Distance histograms
    TH1F* h_distance_2d_all = new TH1F("h_distance_2d_all", "Nearest 2D Distance in Covered Plane;Distance (cm);Entries", 
                                       100, 0, 20);
    h_distance_2d_all->SetLineColor(kRed);
    h_distance_2d_all->SetFillColor(kRed);
    h_distance_2d_all->SetFillStyle(3005);
    
    // NEW: Cluster length histograms
    TH1F* h_length_covering = new TH1F("h_length_covering", "Length of Covering Clusters;Length (cm);Entries", 
                                       100, 0, 500);
    h_length_covering->SetLineColor(kGreen);
    h_length_covering->SetFillColor(kGreen);
    h_length_covering->SetFillStyle(3006);
    
    TH1F* h_length_covered = new TH1F("h_length_covered", "Length of Covered Clusters;Length (cm);Entries", 
                                      100, 0, 500);
    h_length_covered->SetLineColor(kMagenta);
    h_length_covered->SetFillColor(kMagenta);
    h_length_covered->SetFillStyle(3007);
    
    // NEW: Time slice range histograms
    TH1F* h_time_range_covering = new TH1F("h_time_range_covering", "Time Slice Range of Covering Clusters;Time Range;Entries", 
                                           100, 0, 200);
    h_time_range_covering->SetLineColor(kCyan);
    
    TH1F* h_time_range_covered = new TH1F("h_time_range_covered", "Time Slice Range of Covered Clusters;Time Range;Entries", 
                                          100, 0, 200);
    h_time_range_covered->SetLineColor(kOrange);
    
    // Distance by plane histograms
    TH1F* h_3d_distance_u = new TH1F("h_3d_distance_u", "3D Distance - U Plane Coverage;Distance (cm);Entries", 
                                     100, 0, 50);
    h_3d_distance_u->SetLineColor(kRed);
    
    TH1F* h_3d_distance_v = new TH1F("h_3d_distance_v", "3D Distance - V Plane Coverage;Distance (cm);Entries", 
                                     100, 0, 50);
    h_3d_distance_v->SetLineColor(kGreen);
    
    TH1F* h_3d_distance_w = new TH1F("h_3d_distance_w", "3D Distance - W Plane Coverage;Distance (cm);Entries", 
                                     100, 0, 50);
    h_3d_distance_w->SetLineColor(kMagenta);
    
    // Coverage ratio histogram
    TH1F* h_coverage_ratio = new TH1F("h_coverage_ratio", "Coverage Ratio Distribution;Coverage Ratio;Entries", 
                                      50, 0.5, 1.0);
    h_coverage_ratio->SetLineColor(kBlack);
    h_coverage_ratio->SetFillColor(kYellow);
    h_coverage_ratio->SetFillStyle(3003);
    
    // NEW: 2D correlation plots
    TH2F* h2_3d_vs_2d = new TH2F("h2_3d_vs_2d", "3D vs 2D Distance Correlation;2D Distance (cm);3D Distance (cm)", 
                                  50, 0, 20, 50, 0, 50);
    
    TH2F* h2_length_correlation = new TH2F("h2_length_correlation", "Covering vs Covered Cluster Length;Covered Length (cm);Covering Length (cm)", 
                                           50, 0, 500, 50, 0, 500);
    
    TH2F* h2_dist_coverage = new TH2F("h2_dist_coverage", "3D Distance vs Coverage Ratio;Coverage Ratio;3D Distance (cm)", 
                                      50, 0.5, 1.0, 50, 0, 50);
    
    // NEW: Profile plots
    TProfile* prof_length_vs_distance = new TProfile("prof_length_vs_distance", "Average 3D Distance vs Covered Cluster Length;Covered Cluster Length (cm);Average 3D Distance (cm)", 
                                                     50, 0, 500, 0, 50);
    prof_length_vs_distance->SetLineColor(kBlue);
    prof_length_vs_distance->SetMarkerColor(kBlue);
    
    // Fill histograms using tree
    tree->Draw("nearest_3d_distance_cm>>h_distance_3d_all", "", "goff");
    tree->Draw("nearest_2d_distance_cm>>h_distance_2d_all", "", "goff");                              // NEW
    tree->Draw("cluster1_length_cm>>h_length_covering", "", "goff");                                  // NEW
    tree->Draw("cluster2_length_cm>>h_length_covered", "", "goff");                                   // NEW
    tree->Draw("(cluster1_time_max-cluster1_time_min)>>h_time_range_covering", "", "goff");          // NEW
    tree->Draw("(cluster2_time_max-cluster2_time_min)>>h_time_range_covered", "", "goff");           // NEW
    tree->Draw("nearest_3d_distance_cm>>h_3d_distance_u", "coverage_plane==\"U\"", "goff");
    tree->Draw("nearest_3d_distance_cm>>h_3d_distance_v", "coverage_plane==\"V\"", "goff");
    tree->Draw("nearest_3d_distance_cm>>h_3d_distance_w", "coverage_plane==\"W\"", "goff");
    tree->Draw("coverage_ratio>>h_coverage_ratio", "", "goff");
    tree->Draw("nearest_3d_distance_cm:nearest_2d_distance_cm>>h2_3d_vs_2d", "", "goff");            // NEW
    tree->Draw("cluster1_length_cm:cluster2_length_cm>>h2_length_correlation", "", "goff");          // NEW
    tree->Draw("nearest_3d_distance_cm:coverage_ratio>>h2_dist_coverage", "", "goff");
    tree->Draw("nearest_3d_distance_cm:cluster2_length_cm>>prof_length_vs_distance", "", "goff");    // NEW
    
    // Create enhanced canvases and draw plots
    std::cout << "Creating enhanced plots..." << std::endl;
    
    // Canvas 1: Distance distributions (3D and 2D)
    TCanvas* c1 = new TCanvas("c1", "Distance Distributions", 1200, 600);
    c1->Divide(2, 1);
    
    c1->cd(1);
    h_distance_3d_all->Draw();
    h_distance_3d_all->SetTitle("Nearest 3D Distance Between Covered Clusters");
    TPaveText* stats1 = new TPaveText(0.6, 0.7, 0.9, 0.9, "NDC");
    stats1->AddText(Form("Entries: %d", (int)h_distance_3d_all->GetEntries()));
    stats1->AddText(Form("Mean: %.2f cm", h_distance_3d_all->GetMean()));
    stats1->AddText(Form("RMS: %.2f cm", h_distance_3d_all->GetRMS()));
    stats1->Draw();
    
    c1->cd(2);
    h_distance_2d_all->Draw();
    h_distance_2d_all->SetTitle("Nearest 2D Distance in Covered Plane");
    TPaveText* stats2 = new TPaveText(0.6, 0.7, 0.9, 0.9, "NDC");
    stats2->AddText(Form("Entries: %d", (int)h_distance_2d_all->GetEntries()));
    stats2->AddText(Form("Mean: %.2f cm", h_distance_2d_all->GetMean()));
    stats2->AddText(Form("RMS: %.2f cm", h_distance_2d_all->GetRMS()));
    stats2->Draw();
    
    c1->SaveAs("distance_distributions.png");
    c1->SaveAs("distance_distributions.pdf");
    
    // Canvas 2: Cluster length analysis
    TCanvas* c2 = new TCanvas("c2", "Cluster Length Analysis", 1200, 800);
    c2->Divide(2, 2);
    
    c2->cd(1);
    h_length_covering->Draw();
    h_length_covering->SetTitle("Length of Covering Clusters");
    
    c2->cd(2);
    h_length_covered->Draw();
    h_length_covered->SetTitle("Length of Covered Clusters");
    
    c2->cd(3);
    h2_length_correlation->Draw("COLZ");
    h2_length_correlation->SetTitle("Covering vs Covered Cluster Length Correlation");
    
    c2->cd(4);
    prof_length_vs_distance->Draw();
    prof_length_vs_distance->SetTitle("Average 3D Distance vs Covered Cluster Length");
    
    c2->SaveAs("cluster_length_analysis.png");
    c2->SaveAs("cluster_length_analysis.pdf");
    
    // Canvas 3: Time slice analysis
    TCanvas* c3 = new TCanvas("c3", "Time Slice Analysis", 1200, 600);
    c3->Divide(2, 1);
    
    c3->cd(1);
    h_time_range_covering->Draw();
    h_time_range_covering->SetTitle("Time Slice Range - Covering Clusters");
    
    c3->cd(2);
    h_time_range_covered->Draw();
    h_time_range_covered->SetTitle("Time Slice Range - Covered Clusters");
    
    c3->SaveAs("time_slice_analysis.png");
    c3->SaveAs("time_slice_analysis.pdf");
    
    // Canvas 4: 3D Distance by plane
    TCanvas* c4 = new TCanvas("c4", "3D Distance by Plane", 1200, 800);
    c4->Divide(2, 2);
    
    c4->cd(1);
    // gPad->SetLogy();
    h_3d_distance_u->Draw();
    h_3d_distance_u->SetTitle("U Plane Coverage");
    
    c4->cd(2);
    // gPad->SetLogy();
    h_3d_distance_v->Draw();
    h_3d_distance_v->SetTitle("V Plane Coverage");
    
    c4->cd(3);
    // gPad->SetLogy();
    h_3d_distance_w->Draw();
    h_3d_distance_w->SetTitle("W Plane Coverage");
    
    c4->cd(4);
    // Overlay all planes
    h_3d_distance_u->Draw();
    h_3d_distance_v->Draw("same");
    h_3d_distance_w->Draw("same");
    
    TLegend* leg = new TLegend(0.6, 0.7, 0.9, 0.9);
    leg->AddEntry(h_3d_distance_u, "U Plane", "l");
    leg->AddEntry(h_3d_distance_v, "V Plane", "l");
    leg->AddEntry(h_3d_distance_w, "W Plane", "l");
    leg->Draw();
    gPad->SetTitle("All Planes Overlay");
    
    c4->SaveAs("distance_by_plane.png");
    c4->SaveAs("distance_by_plane.pdf");
    
    // Canvas 5: Correlation analysis
    TCanvas* c5 = new TCanvas("c5", "Distance Correlations", 1200, 800);
    c5->Divide(2, 2);
    
    c5->cd(1);
    h2_3d_vs_2d->Draw("COLZ");
    h2_3d_vs_2d->SetTitle("3D vs 2D Distance Correlation");
    
    c5->cd(2);
    h2_dist_coverage->Draw("COLZ");
    h2_dist_coverage->SetTitle("3D Distance vs Coverage Ratio");
    
    c5->cd(3);
    h_coverage_ratio->Draw();
    h_coverage_ratio->SetTitle("Coverage Ratio Distribution");
    
    c5->cd(4);
    // Scatter plot of 2D vs 3D distances
    tree->Draw("nearest_3d_distance_cm:nearest_2d_distance_cm", "", "");
    gPad->SetTitle("2D vs 3D Distance Scatter Plot");
    
    c5->SaveAs("correlation_analysis.png");
    c5->SaveAs("correlation_analysis.pdf");
    
    // Print enhanced summary statistics
    std::cout << "\n=== ENHANCED SUMMARY STATISTICS ===" << std::endl;
    std::cout << "Total entries: " << data_entries << std::endl;
    
    std::cout << "\n3D Distance statistics (all planes):" << std::endl;
    std::cout << "  Mean: " << h_distance_3d_all->GetMean() << " cm" << std::endl;
    std::cout << "  RMS:  " << h_distance_3d_all->GetRMS() << " cm" << std::endl;
    
    std::cout << "\n2D Distance statistics (all planes):" << std::endl;
    std::cout << "  Mean: " << h_distance_2d_all->GetMean() << " cm" << std::endl;
    std::cout << "  RMS:  " << h_distance_2d_all->GetRMS() << " cm" << std::endl;
    
    std::cout << "\nCluster length statistics:" << std::endl;
    std::cout << "  Covering clusters - Mean: " << h_length_covering->GetMean() << " cm, RMS: " << h_length_covering->GetRMS() << " cm" << std::endl;
    std::cout << "  Covered clusters  - Mean: " << h_length_covered->GetMean() << " cm, RMS: " << h_length_covered->GetRMS() << " cm" << std::endl;
    
    std::cout << "\nTime slice range statistics:" << std::endl;
    std::cout << "  Covering clusters - Mean: " << h_time_range_covering->GetMean() << ", RMS: " << h_time_range_covering->GetRMS() << std::endl;
    std::cout << "  Covered clusters  - Mean: " << h_time_range_covered->GetMean() << ", RMS: " << h_time_range_covered->GetRMS() << std::endl;
    
    std::cout << "\nEntries by plane:" << std::endl;
    std::cout << "  U plane: " << h_3d_distance_u->GetEntries() << std::endl;
    std::cout << "  V plane: " << h_3d_distance_v->GetEntries() << std::endl;
    std::cout << "  W plane: " << h_3d_distance_w->GetEntries() << std::endl;
    
    std::cout << "\nCoverage ratio statistics:" << std::endl;
    std::cout << "  Mean: " << h_coverage_ratio->GetMean() << std::endl;
    std::cout << "  RMS:  " << h_coverage_ratio->GetRMS() << std::endl;
    
    // Write everything to ROOT file
    outfile->Write();
    std::cout << "\nResults saved to cluster_coverage_analysis.root" << std::endl;
    std::cout << "Enhanced plots saved as PNG and PDF files" << std::endl;
    
    // Keep ROOT session alive for interactive analysis
    std::cout << "\nEnhanced tree 'coverage_tree' is available for interactive analysis." << std::endl;
    std::cout << "New available variables:" << std::endl;
    std::cout << "  nearest_2d_distance_cm, cluster1_length_cm, cluster2_length_cm" << std::endl;
    std::cout << "  cluster1_time_min, cluster1_time_max, cluster2_time_min, cluster2_time_max" << std::endl;
    std::cout << "\nExample enhanced queries:" << std::endl;
    std::cout << "  coverage_tree->Draw(\"nearest_2d_distance_cm\")" << std::endl;
    std::cout << "  coverage_tree->Draw(\"nearest_3d_distance_cm:nearest_2d_distance_cm\", \"\", \"colz\")" << std::endl;
    std::cout << "  coverage_tree->Draw(\"cluster1_length_cm:cluster2_length_cm\", \"\", \"colz\")" << std::endl;
    std::cout << "  coverage_tree->Draw(\"(cluster1_time_max-cluster1_time_min):(cluster2_time_max-cluster2_time_min)\")" << std::endl;
}